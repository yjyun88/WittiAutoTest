import os
import re
import sys
import time as pytime
from difflib import SequenceMatcher

import cv2
import easyocr
import numpy as np
from airtest.core.api import device, exists, sleep, swipe, touch

from Touch_template import touch_template
from box_ACT import capture_screen
from check_video import is_video_playing
from create_report import create_report, input_excel
from utils import Template, output_path

BASE_RESOLUTION = (1920, 1200)

# MEW list matching strategy tuned from live measurements
LIST_ROI_REL = (0.02, 0.36, 0.98, 0.86)
MEW_SCORE_THRESHOLD = 0.66
MEW_MIN_MARGIN = 0.05
MEW_TAG_SCORE_THRESHOLD = 0.60
MEW_FINAL_SCORE_THRESHOLD = 0.62
MEW_STRONG_SCORE_THRESHOLD = 0.69
MEW_STRONG_MARGIN_THRESHOLD = 0.18
MEW_OCR_SIM_THRESHOLD = 0.55
MEW_STRONG_TAG_FLOOR = 0.58
MEW_STRONG_OCR_FLOOR = 0.40
MEW_OCR_PASS_THRESHOLD = 0.80
MEW_OCR_PASS_FINAL = 0.68
MEW_OCR_PASS_SCORE = 0.68
MEW_CANDIDATE_LIMIT = 8
MAX_SWIPE_ATTEMPTS = 8

_READER = None

before_tpl = Template(r"button_images\mew_cate.png", resolution=BASE_RESOLUTION)
after_tpl = [
    Template(r"button_images\mew_down_9.png", threshold=0.8, resolution=BASE_RESOLUTION),
    Template(r"button_images\mew_home.png", threshold=0.8, resolution=BASE_RESOLUTION),
]
play_tpl = Template(r"button_images\play.png", resolution=BASE_RESOLUTION)


def _report_thumbnail_error(img_path, child_nm, image_folder_abs, message, started_at):
    capture_path, base = capture_screen(img_path, child_nm)
    file_path, wb, ws = create_report()
    thumb_path = os.path.join(image_folder_abs, os.path.basename(img_path))
    input_excel(
        "ERROR",
        child_nm,
        base,
        file_path,
        wb,
        ws,
        capture_path,
        thumb_path,
        error_message=message,
        duration_sec=round(pytime.perf_counter() - started_at, 2),
    )


def _load_bgr(path):
    if not os.path.isfile(path):
        return None
    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def _filename_hint_text(path):
    stem = os.path.splitext(os.path.basename(path or ""))[0]
    if "--" not in stem:
        return ""
    return stem.split("--", 1)[1].replace("_", " ").strip()


def _get_reader():
    global _READER
    if _READER is not None:
        return _READER
    try:
        _READER = easyocr.Reader(["ko", "en"], gpu=True)
    except Exception:
        _READER = easyocr.Reader(["ko", "en"], gpu=False)
    return _READER


def _norm(value):
    return re.sub(r"[^0-9A-Za-z가-힣]", "", str(value or "")).lower()


def _resolve_roi_abs(img_w, img_h):
    x1r, y1r, x2r, y2r = LIST_ROI_REL
    x1 = max(0, int(img_w * x1r))
    y1 = max(0, int(img_h * y1r))
    x2 = min(img_w - 1, int(img_w * x2r))
    y2 = min(img_h - 1, int(img_h * y2r))
    return x1, y1, x2, y2


def _match_candidates_in_roi(src_bgr, tpl_bgr, roi_abs, scale_min=0.7, scale_max=1.4, scale_step=0.05):
    x1, y1, x2, y2 = roi_abs
    crop = src_bgr[y1:y2 + 1, x1:x2 + 1]
    if crop.size == 0:
        return []

    ch, cw = crop.shape[:2]
    best = []
    s = scale_min
    while s <= scale_max + 1e-9:
        tw = max(1, int(tpl_bgr.shape[1] * s))
        th = max(1, int(tpl_bgr.shape[0] * s))
        if tw <= cw and th <= ch:
            tpl = tpl_bgr if abs(s - 1.0) < 1e-9 else cv2.resize(
                tpl_bgr, (tw, th), interpolation=cv2.INTER_CUBIC
            )
            res = cv2.matchTemplate(crop, tpl, cv2.TM_CCOEFF_NORMED)

            # Keep top-2 candidates from each scale quickly.
            flat = res.reshape(-1)
            if flat.size == 0:
                s += scale_step
                continue
            k = 2 if flat.size >= 2 else 1
            idx = np.argpartition(flat, -k)[-k:]
            vals = flat[idx]
            order = np.argsort(vals)[::-1]
            for oi in order:
                ii = int(idx[oi])
                yy = ii // res.shape[1]
                xx = ii % res.shape[1]
                score = float(vals[oi])
                cand = {
                    "score": score,
                    "scale": float(s),
                    "rect": (x1 + xx, y1 + yy, tw, th),
                    "center": (x1 + xx + (tw / 2.0), y1 + yy + (th / 2.0)),
                }
                best.append(cand)
        s += scale_step

    if not best:
        return []

    best.sort(key=lambda c: c["score"], reverse=True)
    distinct = []
    for cand in best:
        keep = True
        for existing in distinct:
            ex, ey = existing["center"]
            cx, cy = cand["center"]
            if abs(ex - cx) <= 30 and abs(ey - cy) <= 30:
                keep = False
                break
        if keep:
            distinct.append(cand)
        if len(distinct) >= MEW_CANDIDATE_LIMIT:
            break
    return distinct


def _tag_strip(img_bgr):
    if img_bgr is None or img_bgr.size == 0:
        return None
    h, w = img_bgr.shape[:2]
    y1 = max(0, int(h * 0.72))
    y2 = min(h, int(h * 0.96))
    x1 = max(0, int(w * 0.08))
    x2 = min(w, int(w * 0.92))
    if y2 <= y1 or x2 <= x1:
        return None
    return img_bgr[y1:y2, x1:x2]


def _tag_score(src_bgr, tpl_bgr, rect):
    x, y, w, h = rect
    x1 = max(0, int(x))
    y1 = max(0, int(y))
    x2 = min(src_bgr.shape[1], int(x + w))
    y2 = min(src_bgr.shape[0], int(y + h))
    if x2 <= x1 or y2 <= y1:
        return 0.0

    src_patch = src_bgr[y1:y2, x1:x2]
    src_tag = _tag_strip(src_patch)
    tpl_tag = _tag_strip(tpl_bgr)
    if src_tag is None or tpl_tag is None:
        return 0.0

    th, tw = tpl_tag.shape[:2]
    if src_tag.shape[1] < tw or src_tag.shape[0] < th:
        src_tag = cv2.resize(src_tag, (tw, th), interpolation=cv2.INTER_CUBIC)
    else:
        src_tag = cv2.resize(src_tag, (tw, th), interpolation=cv2.INTER_AREA)

    src_gray = cv2.cvtColor(src_tag, cv2.COLOR_BGR2GRAY)
    tpl_gray = cv2.cvtColor(tpl_tag, cv2.COLOR_BGR2GRAY)
    src_edge = cv2.Canny(src_gray, 80, 160)
    tpl_edge = cv2.Canny(tpl_gray, 80, 160)

    gray_score = float(cv2.matchTemplate(src_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)[0][0])
    edge_score = float(cv2.matchTemplate(src_edge, tpl_edge, cv2.TM_CCOEFF_NORMED)[0][0])
    return (gray_score * 0.65) + (edge_score * 0.35)


def _extract_text_hint(tpl_bgr):
    try:
        results = _get_reader().readtext(tpl_bgr, detail=1)
    except Exception:
        return ""
    best_text = ""
    best_prob = -1.0
    for _bbox, text, prob in results:
        norm_text = _norm(text)
        if len(norm_text) < 2:
            continue
        if float(prob) > best_prob:
            best_prob = float(prob)
            best_text = text
    return best_text


def _ocr_similarity(src_bgr, rect, text_hint):
    hint = _norm(text_hint)
    if not hint:
        return 1.0

    x, y, w, h = rect
    pad_x = max(10, int(w * 0.25))
    pad_y = max(10, int(h * 0.25))
    x1 = max(0, int(x - pad_x))
    y1 = max(0, int(y - pad_y))
    x2 = min(src_bgr.shape[1], int(x + w + pad_x))
    y2 = min(src_bgr.shape[0], int(y + h + pad_y))
    patch = src_bgr[y1:y2, x1:x2]
    if patch.size == 0:
        return 0.0

    try:
        results = _get_reader().readtext(patch, detail=1)
    except Exception:
        return 0.0

    best_sim = 0.0
    for _bbox, text, _prob in results:
        norm_text = _norm(text)
        if not norm_text:
            continue
        sim = SequenceMatcher(None, norm_text, hint).ratio()
        if sim > best_sim:
            best_sim = sim
    return best_sim


def _roi_change_score(prev_bgr, curr_bgr):
    if prev_bgr is None or curr_bgr is None:
        return 100.0
    h = min(prev_bgr.shape[0], curr_bgr.shape[0])
    w = min(prev_bgr.shape[1], curr_bgr.shape[1])
    if h <= 0 or w <= 0:
        return 100.0
    a = cv2.cvtColor(prev_bgr[:h, :w], cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(curr_bgr[:h, :w], cv2.COLOR_BGR2GRAY)
    return float(np.mean(cv2.absdiff(a, b)))


def _find_and_touch_mew_item(template_path):
    src = device().snapshot()
    tpl = _load_bgr(template_path)
    if src is None or tpl is None:
        return False

    h, w = src.shape[:2]
    roi_abs = _resolve_roi_abs(w, h)
    candidates = _match_candidates_in_roi(src, tpl, roi_abs)
    if not candidates:
        return False

    text_hint = _filename_hint_text(template_path) or _extract_text_hint(tpl)
    accepted = None
    accepted_log = ""
    fallback = None
    fallback_rank = -1.0
    fallback_log = ""

    for idx, cand in enumerate(candidates):
        next_score = candidates[idx + 1]["score"] if idx + 1 < len(candidates) else 0.0
        margin = float(cand["score"] - next_score)
        tag_score = _tag_score(src, tpl, cand["rect"])
        ocr_sim = _ocr_similarity(src, cand["rect"], text_hint)
        final_score = (cand["score"] * 0.30) + (tag_score * 0.35) + (ocr_sim * 0.35)
        strong_primary_match = (
            cand["score"] >= MEW_STRONG_SCORE_THRESHOLD
            and margin >= MEW_STRONG_MARGIN_THRESHOLD
        )
        cand_log = (
            f"score={cand['score']:.3f} tag={tag_score:.3f} ocr={ocr_sim:.3f} "
            f"final={final_score:.3f} margin={margin:.3f} strong={strong_primary_match} "
            f"scale={cand['scale']:.2f}"
        )

        if final_score > fallback_rank:
            fallback = cand
            fallback_rank = final_score
            fallback_log = cand_log

        if (
            cand["score"] >= MEW_SCORE_THRESHOLD
            and (
                (
                    ocr_sim >= MEW_OCR_PASS_THRESHOLD
                    and final_score >= MEW_OCR_PASS_FINAL
                    and cand["score"] >= MEW_OCR_PASS_SCORE
                )
                or (
                    margin >= MEW_MIN_MARGIN
                    and (
                        (
                            strong_primary_match
                            and (
                                tag_score >= MEW_STRONG_TAG_FLOOR
                                or ocr_sim >= MEW_STRONG_OCR_FLOOR
                            )
                        )
                        or (
                            tag_score >= MEW_TAG_SCORE_THRESHOLD
                            and final_score >= MEW_FINAL_SCORE_THRESHOLD
                            and ocr_sim >= MEW_OCR_SIM_THRESHOLD
                        )
                    )
                )
            )
        ):
            accepted = cand
            accepted_log = cand_log
            break

    if accepted is None:
        print(
            f"[MEW MATCH] reject {fallback_log}"
        )
        return False

    x, y = accepted["center"]
    print(
        f"[MEW MATCH] pass {accepted_log}"
    )
    touch((int(x), int(y)))
    sleep(1.0)
    return True


def touch_mewlist_images(
    childNm,
    image_folder="downloaded_images",
    before_template=before_tpl,
    after_templates=after_tpl,
):
    """
    Touch mewList thumbnails in order using robust ROI+margin matching.
    """
    image_folder_abs = output_path(image_folder)

    mewlist_images = sorted([
        f for f in os.listdir(image_folder_abs)
        if childNm in f
        and "mewList" in f
        and f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))
    ])

    print(f"총 {len(mewlist_images)}개의 mewList 이미지를 터치 시도합니다.")

    for idx, img_file in enumerate(mewlist_images):
        img_path = os.path.join(image_folder_abs, img_file)
        started_at = pytime.perf_counter()
        try:
            if before_template:
                touch_template(before_template, region_code=7)
            print(f"화면에서 {img_file} 이미지 터치 시도")

            attempts = 0
            touched = False
            prev_screen = device().snapshot()

            while not touched and attempts < MAX_SWIPE_ATTEMPTS:
                if _find_and_touch_mew_item(img_path):
                    touched = True
                else:
                    print(
                        f"'{img_file}' 이미지 터치 실패. 리스트를 스와이프하고 재시도합니다. "
                        f"(시도 {attempts + 1}회 / {MAX_SWIPE_ATTEMPTS}회)"
                    )
                    swipe((0.5, 0.6), vector=[-0.5, 0])
                    sleep(0.8)
                    curr_screen = device().snapshot()
                    diff = _roi_change_score(prev_screen, curr_screen)
                    print(f"[MEW SWIPE] roi change score={diff:.2f}")
                    if diff < 2.0:
                        swipe((0.65, 0.6), vector=[-0.6, 0])
                        sleep(0.8)
                        curr_screen = device().snapshot()
                        diff2 = _roi_change_score(prev_screen, curr_screen)
                        print(f"[MEW SWIPE] fallback change score={diff2:.2f}")
                    prev_screen = curr_screen
                    attempts += 1

            if not touched:
                print(f"'{img_file}' 이미지를 최종적으로 찾지 못했습니다.")
                _report_thumbnail_error(
                    img_path,
                    childNm,
                    image_folder_abs,
                    "thumbnail template not found",
                    started_at,
                )
                continue

            print("======================================== 콘텐츠 실행 대기 ========================================")
            sleep(15)

            if exists(play_tpl):
                touch_template(play_tpl)
                sleep(4)

            video_playing = is_video_playing(timeout=30, interval=0.1, diff_threshold=0.2)
            capture_path, base = capture_screen(img_path, childNm)

            file_path, wb, ws = create_report()
            class_name = f"{childNm}"
            content_name = f"{base}"
            thumb_path = os.path.join(image_folder_abs, img_file)
            input_excel(
                video_playing,
                class_name,
                content_name,
                file_path,
                wb,
                ws,
                capture_path,
                thumb_path,
                duration_sec=round(pytime.perf_counter() - started_at, 2),
            )
            sleep(5)

            if after_templates:
                for tpl in after_templates:
                    try:
                        ok = touch_template(tpl, region_code=6, threshold=0.8)
                        sleep(1)
                    except Exception:
                        ok = False
                    if not ok:
                        touch_template(Template(r"button_images\mew_down.png"), region_code=6, threshold=0.8)

        except Exception as e:
            print(f"{img_file} 이미지를 못찾거나 터치 실패: {e}")
            return False

    return True
