from airtest.core.api import exists, swipe, touch, snapshot
from airtest.core.error import TargetNotFoundError

from Touch_template import touch_template
from utils import Template, get_ocr_reader
from PIL import Image

import os, re, time, cv2
import numpy as np

from box_ACT import capture_screen
from check_video import is_video_playing
from create_report import create_report, input_excel

BASE_RESOLUTION = (1920, 1200)
BASE_RESOLUTION2 = (2304, 1440)

# 템플릿 미리 로드
step_templates = {
    i: Template(os.path.join(r"button_images\witti_world", f"step{i}.png"), threshold=0.95, resolution=BASE_RESOLUTION)
    for i in range(1, 3)
}
book_templates = {
    i: Template(os.path.join(r"button_images\witti_world", f"{i}.png"), threshold=0.95, resolution=BASE_RESOLUTION)
    for i in range(1, 14)
}
aram_play = Template(r"button_images\aram_play.png", threshold=0.9, resolution=BASE_RESOLUTION)
play_tpl_2 = Template(r"button_images\play.png", resolution=BASE_RESOLUTION)
#recorded_res = (1440, 2304)
action_templates = {
    action: Template(
        os.path.join(r"button_images\witti_world", f"{action}.png"),
        resolution=BASE_RESOLUTION,
        scale_max=2.0,
        scale_step=0.005
        )
    for action in ["감상하기", "이해하기", "생각하기", "표현하기", "독후활동"]
}

DEBUG_DIR = "debug_images"


# STEP 선택, 호 찾기
def select_step(step_num, book_num, width, height):
    """111111
    1) step_num == 2일 때만 단계 이미지 터치
    2) book_num 리스트 이미지를 찾아서 좌표 반환
    """
    # 단계 이미지 터치
    if step_num:
        step_tpl = step_templates.get(step_num)
        try:
            touch(step_tpl)
            print(f"STEP {step_num} 선택")
            time.sleep(1)
        except Exception as e:
            print(f"STEP {step_num} 선택 상태")

    # 리스트 이미지 찾기 + 스크롤 재시도
    book_tpl = book_templates.get(book_num)
    tpl_bgr = imread_unicode(book_tpl.filename)
    tpl_h, tpl_w = tpl_bgr.shape[:2]
    start_pos = (width // 2, int(height * 0.8))
    end_pos   = (width // 2, int(height * 0.2))

    while True:
        screen_path = os.path.join(DEBUG_DIR, "select_step_temp.png")
        snapshot(screen_path)
        screen = cv2.imread(screen_path)
        os.remove(screen_path)

        max_val, max_loc, scale = match_multi_scale(
            screen, tpl_bgr,
            threshold=0.6,
            scale_min=0.65,
            scale_max=1.35,
            scale_step=0.02,
        )
        if max_loc is not None:
            ocr_ok, ocr_text = verify_number_by_ocr(screen, max_loc, tpl_w, tpl_h, scale, book_num)
            if ocr_ok:
                x = max_loc[0] + int(tpl_w * scale) // 2
                y = max_loc[1] + int(tpl_h * scale) // 2
                print(f"[Info] {book_num}호 템플릿 위치 찾음: ({x},{y}) score={max_val:.3f} scale={scale:.2f}")
                return x, y  # x, y 좌표 반환
            print(f"[Info] {book_num}호 이미지 매칭(score={max_val:.3f})은 되었으나 OCR 검증 실패(인식='{ocr_text}') → 스와이프 후 재탐색")
        else:
            print(f"[Info] {book_num}호 템플릿 현재 화면에 없음, 아래로 스와이프")
        swipe(start_pos, end_pos)
        time.sleep(1)


# 배지 디자인이 모든 호(1~13)가 동일해 이미지 매칭만으로는 숫자를 구분하기 어려움
# → 매칭된 영역을 OCR로 재확인해 실제 숫자가 book_num과 일치하는지 검증
def verify_number_by_ocr(screen, loc, tpl_w, tpl_h, scale, book_num, pad_ratio=0.3):
    sw, sh = int(tpl_w * scale), int(tpl_h * scale)
    pad_x, pad_y = int(sw * pad_ratio), int(sh * pad_ratio)
    img_h, img_w = screen.shape[:2]
    x1 = max(loc[0] - pad_x, 0)
    y1 = max(loc[1] - pad_y, 0)
    x2 = min(loc[0] + sw + pad_x, img_w)
    y2 = min(loc[1] + sh + pad_y, img_h)
    crop = screen[y1:y2, x1:x2]

    try:
        results = get_ocr_reader().readtext(crop, detail=1)
    except Exception as e:
        print(f"[OCR] 인식 실패: {e}")
        return False, ""

    text = "".join(t for _bbox, t, _prob in results)
    digits = re.findall(r"\d+", text)
    matched = str(book_num) in digits
    print(f"[OCR] 인식 텍스트='{text}' digits={digits} 기대값={book_num} → {'일치' if matched else '불일치'}")
    return matched, text


# ROI 생성
def create_roi(find_y, subjCd, itemCd, curtnSeq, height=350):
    """ 
    find_y 위치를 중심으로 세로 높이 `height` 만큼의 ROI를 잘라
    action_templates 내 버튼을 찾아 터치하고 결과 True/False 반환
    """
    # 전체 화면 스크린샷 → 파일 저장
    full_path = os.path.join(DEBUG_DIR, f"roi_temp.png")
    snapshot(full_path)

    # OpenCV 로 읽어오기
    img = cv2.imread(full_path)
    img_h, img_w = img.shape[:2]
    os.remove(full_path)

    # ROI 범위 계산 (클램핑)
    top    = max(find_y - height//2, 0)
    bottom = min(find_y + height//2, img_h)
    left, right = 0, img_w

    # ROI 잘라내기
    roi = img[top:bottom, left:right]

    # ROI 이미지 파일로 저장
    roi_path = os.path.join(DEBUG_DIR, f"roi_{subjCd}_STEP{itemCd}_{curtnSeq}호.png")
    rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    pil_img.save(roi_path)
    print(f"[Debug] ROI saved → {roi_path} (region: x={left}~{right}, y={top}~{bottom})")

    return roi, top


# 템플릿 한글명 처리
def imread_unicode(path):
    pil = Image.open(path)                       # PIL은 한글 경로 지원
    arr = np.asarray(pil)                        # RGB 순서
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)   # BGR 로 변환
    return bgr


# 각 컨텐츠 템플릿 매칭 & 터치
def match_and_touch_roi(roi, top, subjCd, curtnSeq, act_items, saved_files):

    for idx, (action, tpl) in enumerate(action_templates.items(), start=1):
        started_at = time.perf_counter()
        # 템플릿 이미지 로드 (OpenCV BGR)
        tpl_bgr = imread_unicode(tpl.filename)
        if tpl_bgr is None:
            print(f"[Error] template image not found: {tpl.filename}")
            print("Template.filename repr:", repr(tpl.filename))
            continue
        tpl_h, tpl_w = tpl_bgr.shape[:2]

        # 멀티-스케일 매칭
        max_val, max_loc, scale = match_multi_scale(
            roi, tpl_bgr,
            threshold=tpl.threshold,
            scale_min=0.5,       # 필요에 따라 조정
            scale_max=2.0,
            scale_step=0.005
        )
        
        if max_loc is None:
            print(f"[Info] '{action}' 멀티-스케일 매칭 실패")
            continue

        # 매칭된 위치의 중심 좌표 계산
        scaled_w = int(tpl_w * scale)
        scaled_h = int(tpl_h * scale)
        cx = int(max_loc[0] + scaled_w / 2)
        cy = int(max_loc[1] + scaled_h / 2)

        # 전체 화면 좌표로 보정
        global_x = cx
        global_y = cy + top

        print(f"[Info] '{action}' 매칭({max_val:.2f}@{scale:.2f}) → 터치 ({global_x},{global_y})")
        touch((global_x, global_y))
        time.sleep(10)
        
        res = cv2.matchTemplate(roi, tpl_bgr, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)    

        # 플레이 버튼 있으면 터치
        if exists(aram_play):
            try:
                touch_template(aram_play, threshold=0.9)
            except TargetNotFoundError:
                pos = exists(play_tpl_2)
                if pos:
                    touch(pos)
        print("======================================== 컨텐츠 실행 대기 ========================================")
        time.sleep(10)

        # 현재 화면 캡쳐, 컨텐츠 실행 확인
        video_playing = is_video_playing(timeout=30, interval=0.1, diff_threshold=0.2)
        time.sleep(5)
        capture_path, base = capture_screen(img_path="downloaded_images/school_aram", childNm=subjCd)

        # 엑셀 Report 생성, 데이터 삽입
        file_path, wb, ws = create_report()
        time.sleep(1)
        class_name = f"{subjCd} {curtnSeq}호"
        content_name = act_items[idx-1]["actTag"]
        thumb_path = saved_files[idx-1]
        input_excel(
            video_playing, 
            class_name, 
            content_name,
            file_path,
            wb,
            ws,
            capture_path,
            thumb_path,
            duration_sec=round(time.perf_counter() - started_at, 2),
        )
        time.sleep(1)

        # 컨텐츠 종료
        touch_template(Template(r"button_images\aram_exit.png", resolution=BASE_RESOLUTION), region_code=1)
        time.sleep(5)

    # 어느 버튼도 못 찾았으면 False
    return False


def match_multi_scale(roi, tpl_bgr, threshold=0.8,
                      scale_min=0.5, scale_max=2.0, scale_step=0.01):
    """
    roi      : BGR numpy array (잘라낸 영역)
    tpl_bgr  : BGR numpy array (원본 템플릿)
    threshold: 매칭 성공 임계치
    scale_min, scale_max, scale_step: 배율 탐색 범위 및 단위
    returns  : (best_val, best_loc, best_scale) or (None, None, None)
    """
    best_val, best_loc, best_scale = 0, None, None
    h, w = tpl_bgr.shape[:2]
    roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    tpl_gray = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2GRAY)
    for s in np.arange(scale_min, scale_max + 1e-6, scale_step):
        tw, th = int(w * s), int(h * s)
        if tw < 10 or th < 10:
            continue
        small = cv2.resize(tpl_gray, (tw, th), interpolation=cv2.INTER_AREA)
        res   = cv2.matchTemplate(roi_gray, small, cv2.TM_CCOEFF_NORMED)
        _, v, _, loc = cv2.minMaxLoc(res)
        if v > best_val:
            best_val, best_loc, best_scale = v, loc, s

    if best_val >= threshold:
        return best_val, best_loc, best_scale
    return None, None, None
