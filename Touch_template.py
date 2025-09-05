from airtest.core.api import *
from airtest.core.settings import Settings as ST
import time
from airtest.core.cv import Template as AirtestTemplate

def touch_template(template,
                   region_code: int | None = 5,   # ← 기본값 None: ROI 미적용
                   max_retries: int = 5,
                   wait: float = 3.0,
                   # scale options
                   scale_min: float = 0.7,
                   scale_max: float = 1.3,
                   scale_step: float = 0.01,
                   center_ratio: float = 0.5,
                   quad_sub_ratio: float = 0.5,
                   after_touch_sleep: float = 1.0,
                   threshold: float | None = None) -> bool:
    """
    template: Airtest Template 객체 또는 이미지 경로(str)
    threshold: 문자열 템플릿 생성 시 사용, 또는 기존 Template.threshold 덮어쓰기

    region_code (옵션):
        None → ROI 제한 없음 (전역 탐색)
        0 = 중앙 박스 (center_ratio)
        1 = 좌상, 2 = 우상, 3 = 좌하, 4 = 우하
        5 = 전체 화면(ROI=풀스크린으로 제한)
        6 = 우상 사분면 내부의 우상 서브 ROI (quad_sub_ratio)
        7 = 중앙 수직 60% 영역 (좌우는 전체)
    """

    # --- Template 인자 정규화 ---
    if isinstance(template, str):
        tpl = AirtestTemplate(template, threshold=threshold) if threshold is not None else AirtestTemplate(template)
    else:
        tpl = template
        if threshold is not None:
            try:
                tpl.threshold = threshold
            except Exception:
                pass

    # --- 스케일 옵션 백업/적용 ---
    had_min  = hasattr(tpl, "scale_min")
    had_max  = hasattr(tpl, "scale_max")
    had_step = hasattr(tpl, "scale_step")
    old_min  = getattr(tpl, "scale_min", None)
    old_max  = getattr(tpl, "scale_max", None)
    old_step = getattr(tpl, "scale_step", None)
    old_strategy = ST.CVSTRATEGY[:] if isinstance(ST.CVSTRATEGY, list) else [ST.CVSTRATEGY]

    tpl.scale_min  = scale_min
    tpl.scale_max  = scale_max
    tpl.scale_step = scale_step
    if not ST.CVSTRATEGY or (isinstance(ST.CVSTRATEGY, list) and ST.CVSTRATEGY[0] != "mstpl"):
        ST.CVSTRATEGY = ["mstpl"] + [s for s in old_strategy if s != "mstpl"]

    # --- ROI 계산 (필요할 때만) ---
    allowed_codes = {0, 1, 2, 3, 4, 5, 6, 7}
    use_roi = region_code in allowed_codes

    if use_roi:
        w, h = G.DEVICE.get_current_resolution()
        cx, cy = w // 2, h // 2
        roi = (0, 0, w - 1, h - 1)

        if region_code == 0:  # 중앙 박스
            bw = max(1, int(w * center_ratio))
            bh = max(1, int(h * center_ratio))
            x1 = max(0, cx - bw // 2)
            y1 = max(0, cy - bh // 2)
            x2 = min(w - 1, x1 + bw - 1)
            y2 = min(h - 1, y1 + bh - 1)
            roi = (x1, y1, x2, y2)
        elif region_code == 1:  # 좌상
            roi = (0, 0, cx - 1, cy - 1)
        elif region_code == 2:  # 우상
            roi = (cx, 0, w - 1, cy - 1)
        elif region_code == 3:  # 좌하
            roi = (0, cy, cx - 1, h - 1)
        elif region_code == 4:  # 우하
            roi = (cx, cy, w - 1, h - 1)
        elif region_code == 5:  # 전체 (명시적)
            roi = (0, 0, w - 1, h - 1)
        elif region_code == 6:  # 우상 사분면 내부의 우상 서브 ROI
            qx1, qy1, qx2, qy2 = cx, 0, w - 1, cy - 1
            q_w = qx2 - qx1 + 1
            q_h = qy2 - qy1 + 1
            sub_w = int(max(1, q_w * quad_sub_ratio))
            sub_h = int(max(1, q_h * quad_sub_ratio))
            x1 = qx2 - sub_w + 1
            y1 = qy1
            x2 = qx2
            y2 = qy1 + sub_h - 1
            roi = (x1, y1, x2, y2)
        elif region_code == 7:  # 중앙 수직 60% 영역
            region_h = int(h * 0.5)
            y1 = max(0, cy - region_h // 2)
            y2 = min(h - 1, y1 + region_h - 1)
            roi = (0, y1, w - 1, y2)

        x1, y1, x2, y2 = roi  # 좌표 언패킹

    try:
        for attempt in range(1, max_retries + 1):
            pos = exists(tpl)
            if pos:
                x, y = pos
                if not use_roi or (x1 <= x <= x2 and y1 <= y <= y2):
                    print(f"[TOUCH] {tpl} at ({x:.0f},{y:.0f}) attempt={attempt}/{max_retries}")
                    touch((int(x), int(y)))
                    if after_touch_sleep > 0:
                        time.sleep(after_touch_sleep)
                    return True
            # ROI를 쓰는 경우인데 범위 밖이면 재시도
            if attempt < max_retries:
                if use_roi:
                    print(f"[WARN] not found {tpl} in ROI {(x1,y1,x2,y2)}, retry {attempt}/{max_retries} after {wait}s")
                else:
                    print(f"[WARN] not found {tpl} (no ROI), retry {attempt}/{max_retries} after {wait}s")
                time.sleep(wait)
            else:
                if use_roi:
                    print(f"[ERROR] {tpl} not found after {max_retries} retries (ROI={(x1,y1,x2,y2)})")
                else:
                    print(f"[ERROR] {tpl} not found after {max_retries} retries (no ROI)")
                return False
    finally:
        # --- 스케일 복구 ---
        try:
            if had_min:  tpl.scale_min  = old_min
            else:        delattr(tpl, "scale_min")
        except AttributeError:
            pass
        try:
            if had_max:  tpl.scale_max  = old_max
            else:        delattr(tpl, "scale_max")
        except AttributeError:
            pass
        try:
            if had_step: tpl.scale_step = old_step
            else:        delattr(tpl, "scale_step")
        except AttributeError:
            pass
        ST.CVSTRATEGY = old_strategy
