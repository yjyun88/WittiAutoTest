from airtest.core.api import exists, swipe, touch, snapshot
from airtest.core.error import TargetNotFoundError

from Touch_template import touch_template
from utils import Template, get_ocr_reader
from PIL import Image

import os, re, time, traceback, unicodedata, cv2
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
# 컨텐츠 진입 시 표시되는 로딩 화면(구름 배경 + 위티 캐릭터).
# 프레임 분석 결과 로딩 화면은 거의 정지 상태이고 컨텐츠 화면도 정지일 수 있어
# 화면 변화량(mean_diff)만으로는 둘을 구분할 수 없다 -> 템플릿으로 판별한다.
# threshold 0.70: 로딩 프레임 최저 0.80, 비로딩 최고 0.43으로 마진 충분 (1920x1200 실측)
aram_exit_tpl = Template(r"button_images\aram_exit.png", resolution=BASE_RESOLUTION)
aram_loading = Template(r"button_images\witti_world\aram_loading.png",
                        threshold=0.70, resolution=BASE_RESOLUTION)
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

# 컨텐츠 진입 후 별도의 플레이 버튼이 뜨는 항목.
# '독후활동'(actTag '5.독후활동/평가')만 플레이 버튼을 거치고,
# 나머지 항목은 터치 즉시 재생되므로 버튼 탐색(최대 30초 폴링)을 건너뛴다.
PLAY_BUTTON_ACTIONS = {"독후활동"}

# 플레이 버튼 터치 후 대기(초).
# 버튼 이후 화면은 로딩 템플릿과 형태가 달라 템플릿으로 판별할 수 없어
# 이 구간만 고정 대기로 컨텐츠가 뜰 시간을 준다.
PLAY_SETTLE_SEC = 3

# 컨텐츠 단위 로그 구분선. 호 단위 구분선(= 96자)보다 좁게 두어 계층을 구분한다.
CONTENT_BAR_WIDTH = 92


def _display_width(text):
    """한글 등 전각 문자를 2칸으로 계산한 표시 폭."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def _content_bar(idx, action, text, blank_before=False):
    """
    컨텐츠 진입/종료를 한 줄 구분선으로 표시한다.
    라벨 길이가 항목마다 다르므로 좌우 '-' 개수를 계산해 전체 폭을 항상 같게 맞춘다.
    """
    if blank_before:
        print("")
    label = f" [{idx}/{len(action_templates)}] '{action}' {text} "
    pad = max(CONTENT_BAR_WIDTH - _display_width(label), 2)
    left = pad // 2
    print("-" * left + label + "-" * (pad - left))


def _on_book_list():
    """호 목록 화면인지 판별한다. 목록 상단의 STEP 탭은 이 화면에만 있다."""
    return any(exists(t) for t in step_templates.values())


def ensure_back_to_list(max_attempts=3):
    """
    컨텐츠 화면에서 호 목록으로 되돌린다. 이미 목록이면 즉시 True.

    컨텐츠 하나가 실패해도 호 전체를 포기하지 않으려면 목록까지만 복귀하면 된다.
    (광장까지 나갔다 다시 들어오는 것은 시간 낭비이고, 컨텐츠 안에서는 광장
     나가기 버튼 자체가 없어 실패한다.)
    """
    for attempt in range(1, max_attempts + 1):
        if _on_book_list():
            return True
        if exists(aram_loading):
            print("[Info] 로딩 화면 감지 → 종료 대기 후 재확인")
            wait_content_loaded(appear_timeout=1)
            continue
        print(f"[Info] 컨텐츠 종료 시도 {attempt}/{max_attempts}")
        if not touch_template(aram_exit_tpl, region_code=1):
            print("[WARN] 컨텐츠 종료 버튼을 찾지 못했습니다")
        time.sleep(3)

    ok = _on_book_list()
    if not ok:
        print("[WARN] 호 목록 화면으로 복귀하지 못했습니다")
    return ok


def _record_failure(subjCd, curtnSeq, action, idx, act_items, saved_files, exc, started_at):
    """
    실패한 컨텐츠도 리포트에 남긴다.
    기록을 건너뛰면 해당 행이 아예 없어져 로그 없이는 누락 자체를 알 수 없다.
    """
    try:
        item = act_items[idx - 1] if idx <= len(act_items) else None
        content_name = (item or {}).get("actTag") or action
        thumb_path = saved_files[idx - 1] if idx <= len(saved_files) else None
        capture_path = None
        try:
            capture_path, _base = capture_screen(img_path="downloaded_images/school_aram", childNm=subjCd)
        except Exception as ce:
            print(f"[WARN] 실패 화면 캡처 실패: {ce}")
        file_path, wb, ws = create_report()
        input_excel(
            "FAIL",
            f"{subjCd} {curtnSeq}호",
            content_name,
            file_path,
            wb,
            ws,
            capture_path,
            thumb_path,
            error_message=f"{type(exc).__name__}: {exc}",
            duration_sec=round(time.perf_counter() - started_at, 2),
        )
    except Exception as e2:
        print(f"[WARN] 실패 기록 실패: {e2}")


def wait_content_loaded(appear_timeout=8, gone_timeout=60, interval=0.5):
    """
    컨텐츠 터치 후 '로딩 화면이 뜨고 다시 사라질 때까지' 기다린다.

    고정 sleep이나 화면 변화량 판정으로는 로딩 화면을 컨텐츠로 오인해
    로딩 중 스크린샷이 리포트에 들어가는 문제가 있었다.

    returns (loaded, seen, elapsed)
      loaded : 컨텐츠 화면까지 도달했는지 (로딩이 끝났거나 애초에 없었음)
      seen   : 로딩 화면을 실제로 본 적이 있는지
      elapsed: 총 소요 시간(초)
    """
    t0 = time.time()

    # 1) 로딩 화면 등장 대기 - 로딩 없이 바로 뜨는 컨텐츠도 있으므로 짧게만 본다
    seen = False
    while time.time() - t0 < appear_timeout:
        if exists(aram_loading):
            seen = True
            break
        time.sleep(interval)

    if not seen:
        print(f"[Info] 로딩 화면 미검출 ({time.time() - t0:.1f}s) -> 컨텐츠 바로 표시된 것으로 간주")
        return True, False, time.time() - t0

    # 2) 로딩 화면 소멸 대기
    print("[Info] 로딩 화면 확인 -> 종료 대기")
    while time.time() - t0 < gone_timeout:
        if not exists(aram_loading):
            elapsed = time.time() - t0
            print(f"[Info] 로딩 종료 확인 (소요 {elapsed:.1f}s) -> 컨텐츠 표시됨")
            return True, True, elapsed
        time.sleep(interval)

    elapsed = time.time() - t0
    print(f"[WARN] 로딩 화면이 {gone_timeout}s 내에 사라지지 않음")
    return False, True, elapsed



# STEP 선택, 호 찾기
def select_step(step_num, book_num, width, height, touch_step=True):
    """111111
    1) step_num 단계 이미지 터치 (touch_step=False면 생략)
    2) book_num 리스트 이미지를 찾아서 좌표 반환

    touch_step: 같은 STEP에서 호만 바꿔가며 진행할 때 False.
                STEP 버튼을 다시 누르면 목록 스크롤이 초기화되어
                매 호마다 처음부터 다시 스크롤 탐색하게 된다.
    """
    # 단계 이미지 터치
    if step_num and touch_step:
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
    # 목록을 아래로 스크롤(다음 호 방향) / 위로 스크롤(이전 호 방향)
    # 위로 스크롤은 아래로 스크롤 좌표를 그대로 뒤집으면 안 된다.
    # 화면 상단에 Step 탭(약 0.20~0.26H)과 과목 서브헤더(약 0.28~0.35H)가 고정으로 있어
    # 시작점이 그 영역에 걸리면 목록이 스크롤되지 않는다 (실기기 SM-F971N 확인).
    # 따라서 위로 스크롤은 목록 내부에서 시작하도록 별도 좌표를 쓴다.
    swipe_fwd = (start_pos, end_pos)
    swipe_bwd = ((width // 2, int(height * 0.4)), (width // 2, int(height * 0.9)))
    direction = swipe_fwd

    max_swipes = 30   # 목록을 한 바퀴 훑기에 충분한 횟수. 초과 시 무한 스와이프 대신 실패 처리
    swipes = 0
    while True:
        screen_path = os.path.join(DEBUG_DIR, "select_step_temp.png")
        snapshot(screen_path)
        screen = cv2.imread(screen_path)
        os.remove(screen_path)

        max_val, max_loc, scale = match_multi_scale(
            screen, tpl_bgr,
            threshold=0.6,
            scale_min=0.6,
            scale_max=1.5,
            scale_step=0.02,
            downscale=0.5,      # 매칭만 축소 (OCR 검증은 원본 화면에서 수행)
        )
        if max_loc is not None:
            ocr_ok, ocr_text = verify_number_by_ocr(screen, max_loc, tpl_w, tpl_h, scale, book_num)
            if ocr_ok:
                x = max_loc[0] + int(tpl_w * scale) // 2
                y = max_loc[1] + int(tpl_h * scale) // 2
                print(f"[Info] {book_num}호 템플릿 위치 찾음: ({x},{y}) score={max_val:.3f} scale={scale:.2f}")
                return x, y  # x, y 좌표 반환
            # 배지 디자인이 모두 같아 다른 호가 매칭될 수 있다.
            # 실제로 읽힌 숫자를 목표값과 비교해 스와이프 방향을 정한다.
            seen = re.findall(r"\d+", _normalize_ocr_digits(ocr_text))
            seen_num = int(seen[0]) if seen else None
            if seen_num is not None and seen_num != book_num:
                direction = swipe_bwd if seen_num > book_num else swipe_fwd
                arrow = "위로" if direction is swipe_bwd else "아래로"
                print(f"[Info] 화면에 {seen_num}호가 보임 (목표 {book_num}호) → {arrow} 스와이프")
            else:
                print(f"[Info] {book_num}호 이미지 매칭(score={max_val:.3f})은 되었으나 OCR 검증 실패(인식='{ocr_text}') → 스와이프 후 재탐색")
        else:
            arrow = "위로" if direction is swipe_bwd else "아래로"
            print(f"[Info] {book_num}호 템플릿 현재 화면에 없음, {arrow} 스와이프")
        swipes += 1
        if swipes > max_swipes:
            raise RuntimeError(f"{book_num}호 항목을 찾지 못했습니다 (스와이프 {max_swipes}회 초과)")
        # duration이 짧으면(기본 0.5초) 앱이 위로 스크롤 제스처를 무시하는 기기가 있다.
        # 실기기(SM-F971N) 확인 결과 0.8초 이상이어야 안정적으로 스크롤된다.
        swipe(*direction, duration=0.9)
        time.sleep(1.2)


# 호 배지의 숫자 글꼴이 한글과 형태가 겹쳐 OCR이 한글로 오인식하는 경우가 있다.
# 예) 4호 배지의 '4'는 '나'로 읽힘 (신뢰도 0.59)
OCR_DIGIT_CONFUSIONS = {
    "나": "4",
    "니": "4",
    "냐": "4",
    "네": "4",
    "ㄴ": "4",
    "l": "1",
    "I": "1",
    "|": "1",
    "O": "0",
    "o": "0",
    "S": "5",
}


def _normalize_ocr_digits(text):
    """OCR이 숫자를 닮은 문자로 잘못 읽은 경우를 숫자로 되돌린다."""
    for src, dst in OCR_DIGIT_CONFUSIONS.items():
        text = text.replace(src, dst)
    return text


# 배지 디자인이 모든 호(1~13)가 동일해 이미지 매칭만으로는 숫자를 구분하기 어려움
# → 매칭된 영역을 OCR로 재확인해 실제 숫자가 book_num과 일치하는지 검증
def verify_number_by_ocr(screen, loc, tpl_w, tpl_h, scale, book_num, pad_ratio=0.3):
    sw, sh = int(tpl_w * scale), int(tpl_h * scale)
    img_h, img_w = screen.shape[:2]

    def _read_box(left, top, right, bottom):
        x1, y1 = max(left, 0), max(top, 0)
        x2, y2 = min(right, img_w), min(bottom, img_h)
        try:
            results = get_ocr_reader().readtext(screen[y1:y2, x1:x2], detail=1)
        except Exception as e:
            print(f"[OCR] 인식 실패: {e}")
            return ""
        return "".join(t for _bbox, t, _prob in results)

    def _read(pad):
        pad_x, pad_y = int(sw * pad), int(sh * pad)
        return _read_box(loc[0] - pad_x, loc[1] - pad_y, loc[0] + sw + pad_x, loc[1] + sh + pad_y)

    # 두 자리 호는 앞자리가 매칭 박스보다 왼쪽에 걸쳐 있어 crop 방식에 따라 오인식이 생긴다.
    #  - 상하 여백을 두면 좌측 퍼즐 홈이 붙어 '11호'가 '71호'로 읽힘
    #  - 여백을 없애면 앞자리가 잘려 '11호'가 '1호'로 읽혀 1호로 오탐됨
    # → 상하 여백 없이 좌측만 넓힌 읽기를 주 판정으로 쓴다 (실기기 SM-F971N 확인)
    target = str(book_num)
    text = _read_box(loc[0] - int(sw * 0.35), loc[1], loc[0] + sw, loc[1] + sh)
    normalized = _normalize_ocr_digits(text)
    digits = re.findall(r"\d+", normalized)
    source = "좌측확장"
    matched = target in digits

    # 주 판정이 불일치면 기존 방식(상하좌우 여백)으로 한 번 더 확인한다.
    # 단, 여백 포함 읽기에서 target을 뒤에 포함하는 더 긴 숫자가 나오면
    # (예: 목표 1, 인식 '11') 앞자리 잘림 오탐이므로 채택하지 않는다.
    if not matched:
        text2 = _read(pad_ratio)
        norm2 = _normalize_ocr_digits(text2)
        digits2 = re.findall(r"\d+", norm2)
        truncated = any(d != target and d.endswith(target) for d in digits)
        if target in digits2 and not truncated:
            text, normalized, digits, source, matched = text2, norm2, digits2, "여백포함", True
    extra = "" if normalized == text else f" (보정='{normalized}')"
    print(f"[OCR/{source}] 인식 텍스트='{text}'{extra} digits={digits} "
          f"기대값={book_num} → {'일치' if matched else '불일치'}")
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
        try:
            started_at = time.perf_counter()
            # API가 돌려준 컨텐츠 수가 템플릿(5개)보다 적을 수 있다.
            # 순번이 없으면 매칭/실행 자체를 하지 않는다 (인덱스 초과 방지).
            if idx > len(act_items):
                print(f"[WARN] '{action}': API 컨텐츠 목록에 {idx}번째 항목이 없어 건너뜁니다 "
                      f"(act_items={len(act_items)})")
                continue
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
                scale_step=0.005,
                cache_key=f"act:{action}",
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

            _content_bar(idx, action, "진입", blank_before=True)
            print(f"[Info] 매칭({max_val:.2f}@{scale:.2f}) → 터치 ({global_x},{global_y})")
            touch((global_x, global_y))

            # 로딩 화면이 끝날 때까지 대기 (컨텐츠가 실제로 뜬 시점을 잡는다)
            loaded, _seen, load_sec = wait_content_loaded()

            # 플레이 버튼은 '독후활동'에서만 나타난다.
            # 다른 항목까지 매번 폴링하면 항목당 최대 30초를 헛되이 쓰게 되므로 건너뛴다.
            actTag = str(act_items[idx-1].get("actTag", "")) if idx <= len(act_items) else ""
            needs_play = action in PLAY_BUTTON_ACTIONS or any(
                a in actTag for a in PLAY_BUTTON_ACTIONS
            )
            if needs_play:
                # 플레이 버튼이 뜰 때까지 폴링 (빠른 기기는 바로 진행, 느린 기기는 최대 30초 확보)
                play_deadline = time.time() + 30
                play_found = False
                while time.time() < play_deadline:
                    if exists(aram_play):
                        play_found = True
                        break
                    time.sleep(0.5)

                if play_found:
                    try:
                        touch_template(aram_play, threshold=0.9)
                    except TargetNotFoundError:
                        pos = exists(play_tpl_2)
                        if pos:
                            touch(pos)
                    # 플레이 버튼 이후 화면은 로딩 템플릿으로 판별할 수 없으므로
                    # 로딩 대기 대신 고정 대기를 준다.
                    print(f"[Info] 플레이 버튼 터치 후 {PLAY_SETTLE_SEC}s 대기")
                    time.sleep(PLAY_SETTLE_SEC)
                else:
                    print("[WARN] 플레이 버튼 30초 내 미확인, 재생 확인 단계로 진행")
            else:
                print(f"[Info] '{action}'은 플레이 버튼 없는 항목 → 버튼 탐색 생략")

            print("[Info] 컨텐츠 실행 확인 중...")

            # 컨텐츠 로드 성공 여부는 '로딩 화면이 끝났는가'로 판정한다.
            # 화면 변화량(is_video_playing)은 로딩 화면과 정지 컨텐츠를 구분하지 못하므로
            # 여기서는 움직임 유무를 참고 정보로만 짧게 확인한다.
            err_msg = None
            if not loaded:
                video_playing = "FAIL"
                err_msg = f"로딩 화면이 끝나지 않음 ({load_sec:.1f}s 대기)"
            else:
                video_playing = is_video_playing(timeout=10, interval=0.1, diff_threshold=0.2)
                if video_playing == "FAIL":
                    # 책 표지처럼 정지 화면으로 시작하는 컨텐츠는 정상이다
                    video_playing = "PASS"
                    err_msg = "정지 화면(움직임 미검출), 컨텐츠 로드는 확인됨"
            capture_path, base = capture_screen(img_path="downloaded_images/school_aram", childNm=subjCd)

            # 엑셀 Report 생성, 데이터 삽입
            file_path, wb, ws = create_report()
            class_name = f"{subjCd} {curtnSeq}호"
            content_name = act_items[idx-1]["actTag"]
            # 썸네일 다운로드가 실패했더라도 기록 자체는 진행한다 (없으면 이미지만 비워둔다)
            thumb_path = saved_files[idx-1] if idx <= len(saved_files) else None
            if thumb_path is None:
                print(f"[WARN] '{action}': 썸네일 파일이 없어 이미지 없이 기록합니다")
            input_excel(
                video_playing, 
                class_name, 
                content_name,
                file_path,
                wb,
                ws,
                capture_path,
                thumb_path,
                error_message=err_msg,
                duration_sec=round(time.perf_counter() - started_at, 2),
            )

            # 컨텐츠 종료 — 반환값을 버리면 종료 실패가 조용히 넘어가고
            # 다음 항목이 컨텐츠 화면에서 시작되어 연쇄 실패가 된다.
            if not touch_template(aram_exit_tpl, region_code=1):
                print("[WARN] 컨텐츠 종료 버튼을 찾지 못했습니다 → 목록 복귀 확인")
            time.sleep(3)
            if not ensure_back_to_list():
                raise RuntimeError(f"'{action}' 종료 후 호 목록으로 복귀하지 못했습니다")
            _content_bar(idx, action,
                         f"종료 [{video_playing}] {time.perf_counter() - started_at:.1f}s")
        except Exception as e:
            # 컨텐츠 하나의 실패가 호 전체를 날리지 않도록 이 항목만 실패로 남기고 진행한다.
            # 목록까지 복귀하지 못하면 화면 상태를 알 수 없으므로 호 단위 처리에 맡긴다.
            print(f"[ERROR] '{action}' 처리 실패: {e}")
            traceback.print_exc()
            _record_failure(subjCd, curtnSeq, action, idx, act_items, saved_files, e, started_at)
            if not ensure_back_to_list():
                raise
            _content_bar(idx, action,
                         f"종료 [FAIL] {time.perf_counter() - started_at:.1f}s")
            print("[Info] 목록 복귀 완료 → 다음 컨텐츠로 진행")

    # 어느 버튼도 못 찾았으면 False
    return False


# 성공한 배율을 (템플릿, 화면크기) 단위로 기억해 다음 탐색을 건너뛴다.
# 기기 해상도가 바뀌면 키가 달라지므로 다른 기기에 잘못 적용될 일은 없다.
_SCALE_CACHE = {}


def _sweep_scales(img_gray, tpl_gray, scales):
    """주어진 배율 목록으로 템플릿 매칭, 최고 점수 (val, loc, scale) 반환."""
    best_val, best_loc, best_scale = 0, None, None
    ih, iw = img_gray.shape[:2]
    h, w = tpl_gray.shape[:2]
    for s in scales:
        tw, th = int(w * s), int(h * s)
        if tw < 10 or th < 10 or tw > iw or th > ih:
            continue
        small = cv2.resize(tpl_gray, (tw, th), interpolation=cv2.INTER_AREA)
        res   = cv2.matchTemplate(img_gray, small, cv2.TM_CCOEFF_NORMED)
        _, v, _, loc = cv2.minMaxLoc(res)
        if v > best_val:
            best_val, best_loc, best_scale = v, loc, s
    return best_val, best_loc, best_scale


def match_multi_scale(roi, tpl_bgr, threshold=0.8,
                      scale_min=0.5, scale_max=2.0, scale_step=0.01,
                      cache_key=None, downscale=None,
                      coarse_step=0.02, fine_span=0.03):
    """
    roi      : BGR numpy array (잘라낸 영역)
    tpl_bgr  : BGR numpy array (원본 템플릿)
    threshold: 매칭 성공 임계치
    scale_min, scale_max, scale_step: 배율 탐색 범위 및 단위(정밀 단위)
    cache_key: 성공 배율을 기억할 키(템플릿 식별자). None이면 캐시 미사용
    downscale: 0~1. 매칭용으로만 화면/템플릿을 축소해 연산량을 줄인다
               (반환 좌표는 원본 해상도 기준으로 복원)
    coarse_step / fine_span: 넓은 간격으로 대략 찾고(coarse) 그 주변만
               정밀 간격으로 재탐색(fine)해 정확도는 유지하면서 속도만 올린다
    returns  : (best_val, best_loc, best_scale) or (None, None, None)
    """
    roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    tpl_gray = cv2.cvtColor(tpl_bgr, cv2.COLOR_BGR2GRAY)

    # 축소 매칭 (축소 후 템플릿이 너무 작아지면 적용하지 않음)
    f = 1.0
    if downscale and 0 < downscale < 1:
        th_min = int(tpl_gray.shape[0] * scale_min * downscale)
        tw_min = int(tpl_gray.shape[1] * scale_min * downscale)
        if th_min >= 10 and tw_min >= 10:
            f = downscale
            roi_gray = cv2.resize(roi_gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
            tpl_gray = cv2.resize(tpl_gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)

    def _restore(loc):
        return (int(loc[0] / f), int(loc[1] / f))

    key = (cache_key, roi.shape[0], roi.shape[1], f) if cache_key else None
    fine_step = scale_step

    # 1) 캐시된 배율 주변만 먼저 확인
    #    캐시 당시 점수보다 확연히 낮으면 (다른 대상에 걸린 것) 캐시를 버리고 전체 재탐색한다.
    #    이 게이트가 없으면 threshold만 겨우 넘긴 엉뚱한 매칭이 정답을 가려버린다.
    if key and key in _SCALE_CACHE:
        s0, v0 = _SCALE_CACHE[key]
        lo = max(scale_min, s0 - fine_step * 2)
        hi = min(scale_max, s0 + fine_step * 2)
        v, loc, s = _sweep_scales(roi_gray, tpl_gray, np.arange(lo, hi + 1e-6, fine_step))
        if loc is not None and v >= max(threshold, v0 - 0.08):
            return v, _restore(loc), s
        # 캐시가 안 맞으면 버리고 전체 탐색으로 폴백
        _SCALE_CACHE.pop(key, None)

    # 2) coarse 탐색 → 주변 fine 재탐색
    step_c = max(coarse_step, fine_step)
    v, loc, s = _sweep_scales(roi_gray, tpl_gray, np.arange(scale_min, scale_max + 1e-6, step_c))
    if loc is not None and fine_step < step_c:
        lo = max(scale_min, s - fine_span)
        hi = min(scale_max, s + fine_span)
        v2, loc2, s2 = _sweep_scales(roi_gray, tpl_gray, np.arange(lo, hi + 1e-6, fine_step))
        if loc2 is not None and v2 > v:
            v, loc, s = v2, loc2, s2

    if loc is not None and v >= threshold:
        if key:
            _SCALE_CACHE[key] = (s, v)
        return v, _restore(loc), s
    return None, None, None
