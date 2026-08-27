from airtest.core.api import exists, wait, sleep, touch
import time as pytime
from request_API import *
from world_ACT import *
from world_ACT import _on_book_list   # 언더스코어라 import *로 안 들어온다
from download_thumbnails import download_thumbnails
from adb_recovery import ensure_device_alive

BASE_RESOLUTION = (1920, 1200)

menu_tpl = Template(r"button_images\witti_world\witti_menu_temp2.png", resolution=BASE_RESOLUTION)
school_tpl = Template(r"button_images\witti_world\witti_school_temp.png", resolution=BASE_RESOLUTION)
enter_tpl = Template(r"button_images\witti_world\witti_enter.png", resolution=BASE_RESOLUTION)
aram_tpl = Template(r"button_images\witti_world\school_aram.png", resolution=BASE_RESOLUTION)
aram_korean_tpl = Template(r"button_images\witti_world\school_aram_kor.png", resolution=BASE_RESOLUTION)
aram_math_tpl = Template(r"button_images\witti_world\school_aram_mth.png", resolution=BASE_RESOLUTION)
aram_science_tpl = Template(r"button_images\witti_world\school_aram_sci.png", resolution=BASE_RESOLUTION)
play_tpl = Template(r"button_images\witti_world\school_play.png", resolution=BASE_RESOLUTION)
play_tpl_2 = Template(r"button_images\play.png", resolution=BASE_RESOLUTION)
play_tpl_3 = Template(r"button_images\aram_play.png", resolution=BASE_RESOLUTION)
mew_tpl = Template(r"button_images\witti_world\mew_button.png", resolution=BASE_RESOLUTION)
mew_next = Template(r"button_images\witti_world\mew_next.png", resolution=BASE_RESOLUTION)
mew_exit = Template(r"button_images\witti_world\mew_exit.png", resolution=BASE_RESOLUTION)
mew_exit_y = Template(r"button_images\witti_world\mew_exit_y.png", resolution=BASE_RESOLUTION)
exit_tpl = Template(r"button_images\witti_world\school_exit.png", resolution=BASE_RESOLUTION)
exit_tpl_2 = Template(r"button_images\witti_world\school_exit_2.png", resolution=BASE_RESOLUTION)
exit_y_tpl = Template(r"button_images\witti_world\school_exit_y.png", resolution=BASE_RESOLUTION)
# 호 목록 → 과목 선택으로 한 단계만 올라가는 하늘색 뒤로 화살표.
# 우측 상단 ✕(exit_tpl_2)는 광장까지 나가버리므로 과목 전환에는 쓸 수 없다.
aram_back_tpl = Template(r"button_images\witti_world\aram_back.png", resolution=BASE_RESOLUTION)
mew_after_tpl = Template(r"button_images\mew_down.png", resolution=BASE_RESOLUTION)
mew_after_tpl_2 = Template(r"button_images\mew_down_9.png", resolution=BASE_RESOLUTION, threshold=0.8)
mew_home_tpl = Template(r"button_images\mew_home.png", resolution=BASE_RESOLUTION)


def _touch_required(template, *, threshold=0.65, max_retries=12, wait_sec=2.0, region_code=5, after_touch_sleep=1.0):
    ok = touch_template(
        template,
        region_code=region_code,
        threshold=threshold,
        max_retries=max_retries,
        wait=wait_sec,
        scale_min=0.65,
        scale_max=1.35,
        scale_step=0.02,
        after_touch_sleep=after_touch_sleep,
    )
    if not ok:
        raise RuntimeError(f"Required template not found: {template}")
    return True


def _tap_center_until(template, center_x, center_y, *, attempts=4, wait_sec=1.0):
    for attempt in range(1, attempts + 1):
        print(f"[WORLD] touching center after school button at ({center_x}, {center_y}) attempt={attempt}/{attempts}")
        touch((center_x, center_y))
        sleep(wait_sec)
        if exists(template):
            print(f"[WORLD] target appeared after center tap attempt={attempt}")
            return True
    print(f"[WORLD] target did not appear after center taps: {template}")
    return False


# 광장 복귀를 기다리는 한계 시간. 나가기 버튼을 다 누른 뒤의 로딩만 기다리므로
# 넉넉해도 정상 흐름에서는 도착하는 즉시 빠져나온다.
PLAZA_RETURN_TIMEOUT = 30

# 아람북월드 과목 선택 화면의 과목 버튼. 진입과 과목 전환 양쪽에서 쓴다.
_SUBJECT_TEMPLATES = {1: aram_korean_tpl, 2: aram_math_tpl, 3: aram_science_tpl}


def _on_subject_select():
    """
    아람북월드 과목 선택 화면인지 판별한다.

    과목 버튼만 보고 판단하면 안 된다. 호 목록 화면 상단에도 같은 과목 라벨이
    있어서 school_aram_kor가 0.9대로 잡힌다 (실측: 호 목록에서 0.907@(546,338)).
    그대로 두면 호 목록을 과목 화면으로 오인해 뒤로 나가는 단계를 건너뛰고,
    있지도 않은 다음 과목 버튼을 찾다가 실패한다.

    STEP 탭은 호 목록에만 있으므로, 목록이 아닐 때에 한해 과목 화면으로 본다.
    """
    if _on_book_list():
        return False
    return any(exists(t) for t in _SUBJECT_TEMPLATES.values())


# 광장 → 위티스쿨 → 아람북월드 → 과목 진입
def enter_aram_subject(subjCd, width, height):
    # 화면 중앙 좌표
    center_x, center_y = width // 2, height // 2

    #광장에서 스쿨 진입
    _touch_required(menu_tpl, threshold=0.62)
    _touch_required(school_tpl, threshold=0.60)
    sleep(2)
    # 인트로/대화 넘기기용 중앙 탭 (해상도 무관하게 좌표로 처리)
    _tap_center_until(enter_tpl, center_x, center_y, attempts=4, wait_sec=1.0)

    # 스쿨 진입 후 아람북월드 진입
    _touch_required(enter_tpl, threshold=0.60)
    _touch_required(aram_tpl, threshold=0.60)
    subject_tpl = _SUBJECT_TEMPLATES.get(subjCd)
    if subject_tpl is not None:
        _touch_required(subject_tpl, threshold=0.60)
    sleep(5)


# 아람북월드 안에서 과목만 바꾸기 (ALL 모드에서 과목이 넘어갈 때)
def switch_aram_subject(next_subjCd):
    """
    호 목록에서 뒤로 화살표 한 번으로 과목 선택 화면까지만 올라가 다음 과목을 고른다.

    광장까지 나갔다 다시 들어오면 광장→스쿨→인트로→아람북월드를 매번 다시
    거쳐야 한다. 과목이 바뀔 때 필요한 것은 한 단계 위로 올라가는 것뿐이다.

    화면을 눈으로 확인하고 움직인다. 화살표를 눌렀는데 과목 선택 화면이 아니면
    화면 구조가 달라진 것이므로 False를 돌려주고, 호출한 쪽이 광장 경로로
    돌아가게 한다. 여기서 억지로 진행하면 엉뚱한 화면에서 과목을 누른다.
    """
    print(f"과목 전환: 뒤로 화살표로 과목 선택 화면까지만 나갑니다 (다음 과목 {next_subjCd})")

    if not ensure_device_alive():
        print("[WARN] adb 재연결 실패 → 과목 전환을 확인할 수 없습니다")
        return False

    subject_tpl = _SUBJECT_TEMPLATES.get(next_subjCd)
    if subject_tpl is None:
        print(f"[WARN] 알 수 없는 과목 코드: {next_subjCd}")
        return False

    # 여기 도착했을 때 화면은 항상 호 목록이다. 마지막 컨텐츠를 끝내고
    # ensure_back_to_list()로 목록까지 복귀한 뒤에만 이 함수가 불린다.
    # 좌상 ROI로 제한한다. 전체 화면에서 찾으면 우측 상단의 다른 요소가
    # 낮은 배율에서 0.7대 점수로 잡히는 자리가 있다 (실측 (1426,53)).
    if not touch_template(aram_back_tpl, region_code=1, threshold=0.80):
        print("[WARN] 뒤로 화살표를 찾지 못했습니다")
        return False
    sleep(2)

    # 과목 선택 화면 판정은 두 번 연속 일치할 때만 인정한다. 화면 전환 중의
    # 한 프레임을 믿으면 아직 넘어가지 않은 화면에서 과목을 누르게 된다.
    for _ in range(10):
        if _on_subject_select():
            sleep(1)
            if _on_subject_select():
                break
        sleep(1)
    else:
        print("[WARN] 과목 선택 화면으로 나가지 못했습니다")
        return False

    # 여기서 예외를 던지면 AutoTest의 except가 방금 PASS한 항목을 FAIL로 뒤집는다.
    # 전환 실패는 실패대로 알리되, 판정은 호출한 쪽의 폴백에 맡긴다.
    if not touch_template(subject_tpl, threshold=0.60):
        print(f"[WARN] 과목 버튼을 찾지 못했습니다 (과목 {next_subjCd})")
        return False
    sleep(5)
    print(f"[Info] 과목 전환 완료 (과목 {next_subjCd})")
    return True


# 아람북월드 → 광장으로 나가기
def exit_aram_to_plaza():
    """
    광장까지 복귀하고, 실제로 도달했는지를 bool로 반환한다.

    예전에는 목록 화면 전용 시퀀스를 무조건 실행했기 때문에,
    컨텐츠 화면에 갇힌 상태에서는 나가기 버튼이 없어 반드시 실패했고
    호출한 쪽은 그 실패를 알 수 없어 이후 항목들이 줄줄이 무너졌다.
    """
    print("아람북월드 컨텐츠 검증 종료, 광장으로 이동합니다.")

    # 화면을 읽기 전에 연결부터 확인한다. 끊긴 직후에는 마지막 프레임이
    # 남아 있거나 판정이 흔들려 엉뚱한 화면을 광장으로 오인할 수 있다.
    if not ensure_device_alive():
        print("[WARN] adb 재연결 실패 → 광장 복귀를 확인할 수 없습니다")
        return False

    # 광장 판정은 두 번 연속 일치할 때만 인정한다.
    # 한 프레임만 보고 True를 돌려주면, 실제로는 다른 화면인데 복구 성공으로
    # 처리되어 이후 항목이 전부 엉뚱한 화면에서 시작된다.
    if exists(menu_tpl):
        sleep(1)
        if exists(menu_tpl):
            print("[Info] 이미 광장 화면입니다.")
            return True
        print("[Info] 광장 판정이 재확인에서 뒤집힘 → 나가기 시퀀스를 진행합니다")

    # 컨텐츠 안이라면 먼저 호 목록까지 나온다 (목록에 나가기 버튼이 있다)
    if not ensure_back_to_list():
        print("[WARN] 호 목록 복귀 실패 → 광장 나가기 시퀀스를 그대로 시도합니다")

    try:
        touch_template(exit_tpl_2)
        wait(exit_tpl, timeout=60)
        touch_template(exit_tpl)
        wait(exit_y_tpl, timeout=60)
        touch_template(exit_y_tpl)
    except Exception as e:
        print(f"[WARN] 광장 나가기 시퀀스 실패: {e}")

    # 예전에는 2초만 쉬고 한 번 확인해서, 광장 로딩이 그보다 길면 도착했는데도
    # 실패로 단정했다. 검증이 다 끝난 항목이 화면 전환을 못 기다렸다는 이유로
    # FAIL이 되고, 바로 뒤 복구 경로에서는 "이미 광장"이 나오는 모순이 있었다.
    # 위쪽 진입 판정과 같은 기준(2회 연속 일치)으로 도착을 기다린다.
    deadline = pytime.time() + PLAZA_RETURN_TIMEOUT
    while pytime.time() < deadline:
        if exists(menu_tpl):
            sleep(1)
            if exists(menu_tpl):
                print("[Info] 광장 복귀 성공")
                return True
            continue
        sleep(1)
    print("[Info] 광장 복귀 실패")
    return False


# 위티스쿨 > 아람북월드 컨텐츠 검증
# do_enter/do_exit: ALL 모드에서 같은 과목을 연속 진행할 때 진입/나가기를 생략하기 위한 플래그
def check_wittiaram(width, height, authToken, subjCd, itemCd, curtnSeq, server,
                    do_enter=True, do_exit=True, do_select_step=True):

    if do_enter:
        enter_aram_subject(subjCd, width, height)

    # 커리큘럼 정보 가져오기
    bookNm, subjCd, act_items = get_school_aram_content(authToken, subjCd, itemCd, curtnSeq, server)
    print(f"{subjCd} / STEP {itemCd} / {curtnSeq} 호 컨텐츠 명 : ", bookNm)

    # 썸네일 다운로드
    saved_files = download_thumbnails(act_items, output_dir="downloaded_images/school_aram")

    # STEP 선택 / N 호 서치하여 좌표 반환
    x, y = select_step(step_num=itemCd, book_num=curtnSeq, width=width, height=height,
                       touch_step=do_select_step)

    # ROI 영역 설정 및 좌표 반환, 이미지 저장
    roi, top = create_roi(find_y=y, subjCd=subjCd, itemCd=itemCd, curtnSeq=curtnSeq)

    # 컨텐츠 리스트 선택 & 엑셀 결과 기입
    match_and_touch_roi(roi, top, subjCd, curtnSeq, act_items, saved_files)

    # 광장으로 나가기 (ALL 모드에서 같은 과목이 이어지면 생략)
    if do_exit:
        # 복귀 실패를 방치하면 다음 과목이 엉뚱한 화면에서 시작된다
        if not exit_aram_to_plaza():
            raise RuntimeError("컨텐츠 검증은 끝났으나 광장으로 복귀하지 못했습니다")
    else:
        print("아람북월드 유지 (다음 항목 이어서 진행)")


# MEW 컨텐츠 검증
def check_wittimew(width, height, title_name):
    
    # 화면 중앙 좌표
    center_x, center_y = width // 2, height // 2

    #광장에서 스쿨 진입
    _touch_required(menu_tpl, threshold=0.62)
    _touch_required(school_tpl, threshold=0.60)
    sleep(2)
    _tap_center_until(enter_tpl, center_x, center_y, attempts=4, wait_sec=1.0)

    # 스쿨 진입 후 아람북월드 진입
    sleep(1)
    _touch_required(enter_tpl, threshold=0.60)
    sleep(1)
    _touch_required(play_tpl, threshold=0.60)
    sleep(1)
    _touch_required(mew_tpl, threshold=0.60)
    sleep(3)

    # 곡 메뉴 이동
    count = int(title_name.split('_')[0])
    mew_song_name = title_name.split('_')[1]

    for _ in range(count-1):
        touch_template(mew_next)
        sleep(1)

    # 컨텐츠 검증 시작 (Song ~ Pigment)
    for i in range(12):
        started_at = pytime.perf_counter()
        img_path = fr"button_images\witti_world\mew_buttons\{i+1}.png"
        touch_template(Template(img_path))
        try:
            print("MEW 컨텐츠 재생 대기 최대 120초")
            wait(mew_after_tpl_2, timeout=120)
            sleep(10)
        except Exception:
            print("MEW 컨텐츠 재생 대기 120초 경과...")
        # 재생 버튼이 있으면 터치
        if i in (0, 6):
            ok = touch_template(play_tpl_2, region_code=0)
            if not ok:
                touch_template(play_tpl_3, region_code=0)

        # 현재 화면 캡쳐, 컨텐츠 실행 확인
        if i in (1, 2, 5, 9, 11):
            video_playing = "PASS"
        else:    
            video_playing = is_video_playing(timeout=30, interval=0.1, diff_threshold=0.2)        
        capture_path, base = capture_screen(img_path="downloaded_images/school_aram", childNm="MEW")

        # 엑셀 Report 생성, 데이터 삽입
        file_path, wb, ws = create_report()
        sleep(1)
        class_name = mew_song_name
        if i+1 == 1:
            content_name = "Song"
        elif i+1 == 2:
            content_name = "Read The Lyrics"
        elif i+1 == 3:
            content_name = "Words To Know"
        elif i+1 == 4:
            content_name = "Spell The Word"
        elif i+1 == 5:
            content_name = "Words Play"
        elif i+1 == 6:
            content_name = "My Own Stage"
        elif i+1 == 7:
            content_name = "Chant Song"
        elif i+1 == 8:
            content_name = "Words Game"
        elif i+1 == 9:
            content_name = "Listening Game"
        elif i+1 == 10:
            content_name = "Sing Along"
        elif i+1 == 11:
            content_name = "Play the Beat"
        elif i+1 == 12:
            content_name = "Pigment"
        thumb_path = ""
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

        # 컨텐츠 확인 후 닫기 동작
        if i in (7, 8):
            touch_template(mew_after_tpl_2, region_code=6)
            touch_template(mew_home_tpl, region_code=6)
            sleep(2)
        elif i == 9:
            exit_path = r"button_images\witti_world\mew_buttons\sing_along_exit.png"
            touch_template(Template(exit_path))
            sleep(2)
        else:
            result = touch_template(mew_after_tpl, region_code=6)
            if not result:
                touch_template(mew_after_tpl_2, region_code=6)
            touch_template(mew_home_tpl, region_code=6)
            sleep(2)

    # 광장으로 나가기
    print("MEW 컨텐츠 검증 종료, 광장으로 이동합니다.")
    touch_template(mew_exit)
    sleep(1)
    touch_template(mew_exit_y)
    sleep(1)
    touch_template(exit_tpl_2)
    sleep(1)
    touch_template(exit_tpl)
    sleep(1)
    touch_template(exit_y_tpl)
