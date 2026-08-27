from airtest.core.api import exists, wait, sleep, touch
import time as pytime
from request_API import *
from world_ACT import *
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
    if subjCd == 1:
        _touch_required(aram_korean_tpl, threshold=0.60)
    elif subjCd == 2:
        _touch_required(aram_math_tpl, threshold=0.60)
    elif subjCd == 3:
        _touch_required(aram_science_tpl, threshold=0.60)
    sleep(5)


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

    sleep(2)
    ok = bool(exists(menu_tpl))
    print(f"[Info] 광장 복귀 {'성공' if ok else '실패'}")
    return ok


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
