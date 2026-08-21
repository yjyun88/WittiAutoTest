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
PASS_SCORE = 0.60
# 이미지 매칭 점수가 이 값 이상이면 OCR 검증을 생략한다.
# 아람 썸네일은 앱이 좌하단에 '생각하기' 오버레이를, 그 위에 콘텐츠 제목을 겹쳐 렌더링해
# OCR이 두 글자를 섞어 읽는 경우가 있다(예: '생각하기' -> '생각하7하하바').
# 색/그레이/에지 복합 점수가 충분히 높으면 오탐 위험이 낮으므로 OCR 단계를 건너뛴다.
OCR_SKIP_SCORE = 0.75
MAX_SWIPE_ATTEMPTS = 8

before_tpl = Template(r"button_images\aram_cate.png", resolution=BASE_RESOLUTION)
after_tpl = [
    Template(r"button_images\aram_exit.png", threshold=0.85, resolution=BASE_RESOLUTION),
    Template(r"button_images\exit_y.png"),
]
aram_play = Template(r"button_images\aram_play.png", threshold=0.8, resolution=BASE_RESOLUTION)


def _build_activity_stage_map(content_info):
    result = {}
    for item in content_info or []:
        list_key = str(item.get("list", "")).strip()
        if not list_key.startswith("aramList_"):
            continue
        result[list_key] = item.get("activityStage")
    return result



def _make_top_right_mask(tpl_shape, h_ratio, w_ratio):
    """템플릿 우상단 코너(카테고리 배지 영역)를 0으로 만든 단일 채널 마스크.

    아람(책놀이터) 썸네일은 앱이 우상단 카테고리 배지(예: '창의 책놀이')를
    동적으로 렌더링하는데, API 썸네일에 박힌 배지와 달라 매칭 점수를 떨어뜨린다.
    이 영역을 매칭에서 제외해 배지 불일치의 영향을 없앤다.
    """
    th, tw = tpl_shape[:2]
    mask = np.full((th, tw), 255, dtype=np.uint8)
    my = max(1, int(th * h_ratio))
    mx = int(tw * (1.0 - w_ratio))
    mask[0:my, mx:tw] = 0
    return mask


def _match_normed(img, tpl, mask):
    """마스크 적용 TM_CCOEFF_NORMED (마스크 영역의 무분산으로 생기는 NaN/inf 정리)."""
    if mask is not None:
        res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED, mask=mask)
    else:
        res = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
    return np.nan_to_num(res, nan=-1.0, posinf=-1.0, neginf=-1.0)


def _best_multimode_match(
    src_bgr,
    tpl_bgr,
    roi_abs,
    scale_min=0.6,
    scale_max=1.9,
    scale_step=0.05,
    x_stretch_min=0.90,
    x_stretch_max=1.20,
    x_stretch_step=0.05,
    mask_top_right=True,
    mask_tr_h_ratio=0.30,
    mask_tr_w_ratio=0.52,
):
    x1, y1, x2, y2 = roi_abs
    crop = src_bgr[y1:y2 + 1, x1:x2 + 1]
    if crop.size == 0:
        return None

    crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    crop_edge = cv2.Canny(crop_gray, 80, 160)

    best = None
    s = scale_min
    while s <= scale_max + 1e-9:
        th = max(1, int(tpl_bgr.shape[0] * s))
        xs = x_stretch_min
        while xs <= x_stretch_max + 1e-9:
            scale_x = s * xs
            tw = max(1, int(tpl_bgr.shape[1] * scale_x))
            if tw > crop.shape[1] or th > crop.shape[0]:
                xs += x_stretch_step
                continue

            tpl = tpl_bgr if abs(scale_x - 1.0) < 1e-9 and abs(s - 1.0) < 1e-9 else cv2.resize(
                tpl_bgr, (tw, th), interpolation=cv2.INTER_CUBIC
            )
            tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
            tpl_edge = cv2.Canny(tpl_gray, 80, 160)

            # 1단계: 마스크 없이 빠르게 위치/스케일 후보 탐색 (mask 파라미터는 느려서 전체 ROI에 쓰지 않음)
            res_color = _match_normed(crop, tpl, None)
            res_gray = _match_normed(crop_gray, tpl_gray, None)
            res_edge = _match_normed(crop_edge, tpl_edge, None)

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
                "scale_x": float(scale_x),
                "scale_y": float(s),
                "x_stretch": float(xs),
            }
            if best is None or cand["score"] > best["score"]:
                best = cand
            xs += x_stretch_step
        s += scale_step

    # 2단계: 최종 후보 위치 주변의 작은 창에서만 우상단 배지를 마스킹해 점수 재계산.
    # (전체 ROI에 mask matchTemplate을 돌리면 ~4배 느려지므로, 작은 창에만 적용해 비용을 없앤다.)
    if best is not None and mask_top_right:
        best = _rescore_masked_top_right(
            best, tpl_bgr, crop, crop_gray, crop_edge,
            x1, y1, mask_tr_h_ratio, mask_tr_w_ratio,
        )
    return best


def _rescore_masked_top_right(
    best, tpl_bgr, crop, crop_gray, crop_edge,
    x1, y1, mask_tr_h_ratio, mask_tr_w_ratio, pad=6,
):
    bx, by, bw, bh = best["rect"]
    if bw <= 0 or bh <= 0:
        return best

    tpl = cv2.resize(tpl_bgr, (bw, bh), interpolation=cv2.INTER_CUBIC)
    tpl_gray = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY)
    tpl_edge = cv2.Canny(tpl_gray, 80, 160)
    tr_mask = _make_top_right_mask(tpl.shape, mask_tr_h_ratio, mask_tr_w_ratio)

    # 후보 위치를 crop 로컬 좌표로 변환 후 ±pad 창을 잘라낸다.
    lx, ly = bx - x1, by - y1
    wx1 = max(0, lx - pad)
    wy1 = max(0, ly - pad)
    wx2 = min(crop.shape[1], lx + bw + pad)
    wy2 = min(crop.shape[0], ly + bh + pad)
    win = crop[wy1:wy2, wx1:wx2]
    if win.shape[0] < bh or win.shape[1] < bw:
        return best

    win_gray = crop_gray[wy1:wy2, wx1:wx2]
    win_edge = crop_edge[wy1:wy2, wx1:wx2]

    rc = _match_normed(win, tpl, tr_mask)
    rg = _match_normed(win_gray, tpl_gray, tr_mask)
    re = _match_normed(win_edge, tpl_edge, tr_mask)
    _, c_val, _, c_loc = cv2.minMaxLoc(rc)
    _, g_val, _, _ = cv2.minMaxLoc(rg)
    _, e_val, _, _ = cv2.minMaxLoc(re)

    nbx = x1 + wx1 + c_loc[0]
    nby = y1 + wy1 + c_loc[1]
    best["color"] = float(c_val)
    best["gray"] = float(g_val)
    best["edge"] = float(e_val)
    best["score"] = (0.5 * float(c_val)) + (0.3 * float(g_val)) + (0.2 * float(e_val))
    best["rect"] = (nbx, nby, bw, bh)
    best["center"] = (nbx + bw / 2.0, nby + bh / 2.0)
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
    score_ok = match["score"] >= PASS_SCORE
    ocr_skipped = match["score"] >= OCR_SKIP_SCORE
    if ocr_skipped:
        ocr_ok, ocr_sim = True, 1.0
    else:
        text_hint = extract_text_hint(tpl)
        ocr_ok, ocr_sim = _ocr_validate(src, match["rect"], text_hint)

    if not score_ok or not layout_ok or not ocr_ok:
        print(
            f"[MATCH] reject score={match['score']:.3f} color={match['color']:.3f} "
            f"gray={match['gray']:.3f} edge={match['edge']:.3f} "
            f"scale_x={match.get('scale_x', match['scale']):.2f} "
            f"scale_y={match.get('scale_y', match['scale']):.2f} "
            f"layout={layout_ok} ocr={ocr_ok} ocr_sim={ocr_sim:.3f}"
        )
        return False

    x, y = match["center"]
    ocr_desc = "skip" if ocr_skipped else f"{ocr_sim:.3f}"
    print(
        f"[MATCH] pass score={match['score']:.3f} color={match['color']:.3f} "
        f"gray={match['gray']:.3f} edge={match['edge']:.3f} "
        f"scale_x={match.get('scale_x', match['scale']):.2f} "
        f"scale_y={match.get('scale_y', match['scale']):.2f} "
        f"ocr={ocr_desc}"
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
    activity_stage_map = _build_activity_stage_map(content_info)

    # 카테고리는 리스트 진입 시 1회만 터치 (컨텐츠 종료 시 리스트 위치가 초기화됨)
    if before_template:
        touch_template(before_template, region_code=7)

    for img_file in aramlist_images:
        img_path = os.path.join(image_folder_abs, img_file)
        started_at = pytime.perf_counter()
        try:
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
            activity_stage = activity_stage_map.get(item_key)
            print(f"[ARAM] item={item_key} activityStage={activity_stage}")
            if activity_stage in ("독후활동/평가",) and exists(aram_play):
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
