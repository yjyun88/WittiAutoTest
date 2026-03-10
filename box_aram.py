import os
import time as pytime
from difflib import SequenceMatcher

import cv2
import numpy as np
from airtest.core.api import device, exists, sleep, swipe, touch, wait

from Touch_template import touch_template
from box_ACT import capture_screen
from check_video import is_video_playing
from create_report import create_report, input_excel, report_thumbnail_error
from utils import (
    Template, output_path,
    get_ocr_reader, norm_text, load_bgr, resolve_roi_abs,
    extract_text_hint, roi_change_score,
)

BASE_RESOLUTION = (1920, 1200)
LIST_ROI_REL = (0.02, 0.36, 0.98, 0.86)
LOW_CANDIDATE_SCORE = 0.45
PASS_SCORE = 0.62
MAX_SWIPE_ATTEMPTS = 8

before_tpl = Template(r"button_images\aram_cate.png", resolution=BASE_RESOLUTION)
after_tpl = [
    Template(r"button_images\aram_exit.png", threshold=0.85, resolution=BASE_RESOLUTION),
    Template(r"button_images\exit_y.png"),
]
aram_play = Template(r"button_images\aram_play.png", threshold=0.8, resolution=BASE_RESOLUTION)


def _build_subject_no_map(content_info):
    result = {}
    for item in content_info or []:
        list_key = str(item.get("list", "")).strip()
        if not list_key.startswith("aramList_"):
            continue
        result[list_key] = item.get("subjectNo")
    return result



def _best_multimode_match(src_bgr, tpl_bgr, roi_abs, scale_min=0.6, scale_max=1.5, scale_step=0.05):
    x1, y1, x2, y2 = roi_abs
    crop = src_bgr[y1:y2 + 1, x1:x2 + 1]
    if crop.size == 0:
        return None

    crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    crop_edge = cv2.Canny(crop_gray, 80, 160)

    best = None
    s = scale_min
    while s <= scale_max + 1e-9:
        tw = max(1, int(tpl_bgr.shape[1] * s))
        th = max(1, int(tpl_bgr.shape[0] * s))
        if tw <= crop.shape[1] and th <= crop.shape[0]:
            tpl = tpl_bgr if abs(s - 1.0) < 1e-9 else cv2.resize(
                tpl_bgr, (tw, th), interpolation=cv2.INTER_CUBIC
            )
            tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
            tpl_edge = cv2.Canny(tpl_gray, 80, 160)

            res_color = cv2.matchTemplate(crop, tpl, cv2.TM_CCOEFF_NORMED)
            res_gray = cv2.matchTemplate(crop_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
            res_edge = cv2.matchTemplate(crop_edge, tpl_edge, cv2.TM_CCOEFF_NORMED)

            _, c_val, _, c_loc = cv2.minMaxLoc(res_color)
            _, g_val, _, _ = cv2.minMaxLoc(res_gray)
            _, e_val, _, _ = cv2.minMaxLoc(res_edge)

            score = (0.5 * float(c_val)) + (0.3 * float(g_val)) + (0.2 * float(e_val))
            cx = x1 + c_loc[0] + (tw / 2.0)
            cy = y1 + c_loc[1] + (th / 2.0)
            cand = {
                "score": score,
                "color": float(c_val),
                "gray": float(g_val),
                "edge": float(e_val),
                "center": (cx, cy),
                "rect": (x1 + c_loc[0], y1 + c_loc[1], tw, th),
                "scale": float(s),
            }
            if best is None or cand["score"] > best["score"]:
                best = cand
        s += scale_step
    return best


def _ocr_validate(src_bgr, rect, text_hint):
    if not text_hint:
        return True, 1.0

    x, y, w, h = rect
    pad_x = max(10, int(w * 0.25))
    pad_y = max(10, int(h * 0.25))
    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(src_bgr.shape[1], x + w + pad_x)
    y2 = min(src_bgr.shape[0], y + h + pad_y)
    patch = src_bgr[y1:y2, x1:x2]
    if patch.size == 0:
        return False, 0.0

    try:
        results = get_ocr_reader().readtext(patch, detail=1)
    except Exception:
        return False, 0.0

    hint = norm_text(text_hint)
    if not hint:
        return True, 1.0

    best_sim = 0.0
    for _bbox, text, _prob in results:
        n = norm_text(text)
        if not n:
            continue
        sim = SequenceMatcher(None, n, hint).ratio()
        if sim > best_sim:
            best_sim = sim
    return best_sim >= 0.55, best_sim


def _layout_validate(center_xy, roi_abs):
    x1, y1, x2, y2 = roi_abs
    cx, cy = center_xy
    if not (x1 <= cx <= x2 and y1 <= cy <= y2):
        return False

    rw = max(1.0, x2 - x1 + 1.0)
    rh = max(1.0, y2 - y1 + 1.0)
    rx = (cx - x1) / rw
    ry = (cy - y1) / rh
    return (0.03 <= rx <= 0.97) and (0.05 <= ry <= 0.97)



def _find_and_touch_aram_item(template_path):
    src = device().snapshot()
    tpl = load_bgr(template_path)
    if src is None or tpl is None:
        return False

    h, w = src.shape[:2]
    roi_abs = resolve_roi_abs(w, h, LIST_ROI_REL)
    match = _best_multimode_match(src, tpl, roi_abs)
    if not match or match["score"] < LOW_CANDIDATE_SCORE:
        return False

    layout_ok = _layout_validate(match["center"], roi_abs)
    text_hint = extract_text_hint(tpl)
    ocr_ok, ocr_sim = _ocr_validate(src, match["rect"], text_hint)
    score_ok = match["score"] >= PASS_SCORE

    if not score_ok or not layout_ok or not ocr_ok:
        print(
            f"[MATCH] reject score={match['score']:.3f} color={match['color']:.3f} "
            f"gray={match['gray']:.3f} edge={match['edge']:.3f} "
            f"layout={layout_ok} ocr={ocr_ok} ocr_sim={ocr_sim:.3f}"
        )
        return False

    x, y = match["center"]
    print(
        f"[MATCH] pass score={match['score']:.3f} color={match['color']:.3f} "
        f"gray={match['gray']:.3f} edge={match['edge']:.3f} scale={match['scale']:.2f}"
    )
    touch((int(x), int(y)))
    sleep(1.0)
    return True


# 아람 커리큘럼 선택
def touch_aramlist_images(
    childNm,
    image_folder="downloaded_images",
    before_template=before_tpl,
    after_templates=after_tpl,
    content_info=None,
):
    """
    downloaded_images 폴더 내 aramList 썸네일 이미지를 순서대로 터치
    """
    image_folder_abs = output_path(image_folder)

    aramlist_images = sorted([
        f for f in os.listdir(image_folder_abs)
        if childNm in f
        and "aramList" in f
        and f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))
    ])

    print(f"총 {len(aramlist_images)}개의 aramList 이미지를 터치 시도합니다.")
    subject_no_map = _build_subject_no_map(content_info)

    for img_file in aramlist_images:
        img_path = os.path.join(image_folder_abs, img_file)
        started_at = pytime.perf_counter()
        try:
            if before_template:
                touch_template(before_template, region_code=7)

            attempts = 0
            touched = False
            prev_screen = device().snapshot()

            while not touched and attempts <= MAX_SWIPE_ATTEMPTS:
                if _find_and_touch_aram_item(img_path):
                    touched = True
                else:
                    print(
                        f"'{img_file}' 이미지 터치 실패. 리스트를 스와이프하고 재시도합니다. "
                        f"(시도 {attempts + 1}회)"
                    )
                    swipe((0.5, 0.6), vector=[-0.5, 0])
                    sleep(0.8)
                    curr_screen = device().snapshot()
                    diff = roi_change_score(prev_screen, curr_screen)
                    print(f"[SWIPE] roi change score={diff:.2f}")
                    if diff < 2.0:
                        swipe((0.65, 0.6), vector=[-0.6, 0])
                        sleep(0.8)
                        curr_screen = device().snapshot()
                        diff2 = roi_change_score(prev_screen, curr_screen)
                        print(f"[SWIPE] fallback change score={diff2:.2f}")
                    prev_screen = curr_screen
                    attempts += 1

            if not touched:
                report_thumbnail_error(
                    img_path,
                    childNm,
                    image_folder_abs,
                    "thumbnail template not found",
                    started_at,
                )
                continue

            print("======================================== 콘텐츠 실행 대기 ========================================")
            wait(Template(r"button_images\aram_exit.png"), timeout=60)
            sleep(10)

            item_key = os.path.splitext(img_file)[0].replace(f"{childNm}_", "", 1)
            subject_no = subject_no_map.get(item_key)
            print(f"[ARAM] item={item_key} subjectNo={subject_no}")
            if subject_no == 5 and exists(aram_play):
                sleep(5)
                touch_template(aram_play)
                sleep(5)

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

            if after_templates:
                for tpl in after_templates:
                    touch_template(tpl)

        except Exception as e:
            print(f"{img_file} 이미지를 못찾거나 터치 실패: {e}")
            return False

    return True
