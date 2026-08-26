# AutoTest.py
import os
import traceback

from airtest.core.api import connect_device, device, time

from TEST_witti_box import check_wittibox
from TEST_witti_world import check_wittiaram, check_wittimew, exit_aram_to_plaza
from download_thumbnails import cleanup_thumbnails
from request_API import get_study_access_auth


# 호 단위 로그 구분선
SEPARATOR = "=" * 96


def _now_hms():
    from datetime import datetime
    return datetime.now().strftime("%H:%M:%S")


def _elapsed_text(sec):
    """경과 시간을 사람이 읽기 쉬운 형태로."""
    sec = int(round(sec))
    if sec < 60:
        return f"{sec}초"
    return f"{sec // 60}분 {sec % 60}초"


def AutoTest_Start(
    btn_name,
    device_name,
    device_label,
    inputId,
    inputPwd,
    subjCd,
    itemCd,
    curtnSeq,
    title_name,
    server,
    study_access_mem_nm=None,
    study_access_mem_id=None,
    study_access_auth_token=None,
    selected_class_id="",
):
    # 0) Connect device
    connect_device(f"Android://127.0.0.1:5037/{device_name}?cap_method=MINICAP")

    # 1) Read current device resolution
    width, height = device().get_current_resolution()
    if height > width:
        width, height = height, width
    print(f"Current device resolution: {width} x {height}")

    server_env = server
    print("Current server:", server_env)
    match server_env:
        case "Prod":
            server = "api"
        case "QA":
            server = "qa-api"
        case "Dev":
            server = "dev-api"
        case _:
            server = "api"

    # Provide report defaults for device/server columns
    os.environ["REPORT_DEVICE"] = str(device_label or device_name or "")
    os.environ["REPORT_SERVER_ENV"] = str(server_env or "")
    step_by_button = {
        "pushButton_2": "위티박스",
        "pushButton_3": "아람북월드",
        "pushButton_7": "MEW",
    }
    os.environ["REPORT_STEP"] = step_by_button.get(btn_name, "")

    # 4) Use memNm, memId and authToken saved by study/access
    mem_nm, mem_id, saved_auth_token = get_study_access_auth()
    mem_nm = study_access_mem_nm or mem_nm
    mem_id = study_access_mem_id or mem_id
    authToken = study_access_auth_token or saved_auth_token
    if not authToken:
        print("[ERROR] study/access authToken is missing. Cannot run test.")
        return
    print("Using study/access authToken:", authToken[:12] + "...")

    # 5) Cleanup downloaded thumbnail directory before test
    cleanup_thumbnails()
    time.sleep(1)

    if btn_name == "pushButton_5":
        # 6) WittiBox content validation
        if not mem_id or not mem_nm:
            print("[ERROR] study/access memId/memNm is missing. Cannot run WittiBox test.")
            return
        ok = check_wittibox([mem_id], [mem_nm], authToken, server, inputId, selected_class_id)
        if not ok:
            print("[ERROR] WittiBox test stopped due to class selection failure.")
            return

    elif btn_name == "pushButton_3":
        # 7-1) Arambook world content validation
        # 과목/STEP/호 각각 0이면 ALL (전체 반복)
        subj_names = {1: "한글", 2: "수학", 3: "창의"}
        subj_list = [1, 2, 3] if subjCd == 0 else [subjCd]
        item_list = [1, 2] if itemCd == 0 else [itemCd]
        curtn_list = list(range(1, 14)) if curtnSeq == 0 else [curtnSeq]

        combos = [(sj, it, ct) for sj in subj_list for it in item_list for ct in curtn_list]
        total = len(combos)
        is_all = total > 1

        # 같은 과목이 이어지는 동안에는 아람북월드에서 나가지 않고 STEP/호만 바꿔가며 진행
        need_enter = True
        prev_step = None   # 직전에 화면에서 선택된 STEP
        for idx, (sj, it, ct) in enumerate(combos, start=1):
            next_combo = combos[idx] if idx < total else None
            do_exit = (next_combo is None) or (next_combo[0] != sj)
            # STEP 버튼은 재진입했거나 STEP이 바뀔 때만 누른다
            # (매번 누르면 호 목록 스크롤이 초기화되어 처음부터 다시 탐색)
            do_select_step = need_enter or it != prev_step
            label = f"{subj_names.get(sj, sj)} / STEP {it} / {ct}호"
            # 호 단위 시작/종료 구분선 (ALL이든 단일이든 항상 출력해
            #  긴 로그에서 각 호의 경계를 바로 찾을 수 있게 한다)
            print("")
            print(SEPARATOR)
            print(f"▶ [{idx}/{total}] {label} 시작   {_now_hms()}")
            if not do_select_step:
                print(f"    └ STEP {it} 유지 (호 목록 스크롤 유지하여 이어서 탐색)")
            started_at = time.time()
            result_mark, result_text = "■", "완료"
            try:
                check_wittiaram(width, height, authToken, sj, it, ct, server,
                                do_enter=need_enter, do_exit=do_exit,
                                do_select_step=do_select_step)
                need_enter = do_exit
                prev_step = None if do_exit else it
            except Exception as e:
                result_mark, result_text = "X", "실패"
                print(f"[ERROR] {label} 검증 실패: {e}")
                traceback.print_exc()
                if not is_all:
                    raise
                # 여기까지 올라온 예외는 컨텐츠 단위 복구(목록 복귀)로도 못 살린 경우다.
                # 광장 복귀까지 실패하면 화면 상태를 알 수 없어 남은 항목이 모두
                # 무의미하게 실패하므로 ALL 진행을 중단한다.
                recovered = False
                try:
                    recovered = exit_aram_to_plaza()
                except Exception as e2:
                    print(f"[WARN] 광장 복귀 중 오류: {e2}")
                if not recovered:
                    print(f"X [{idx}/{total}] {label} 실패   "
                          f"(소요 {_elapsed_text(time.time() - started_at)})")
                    print(SEPARATOR)
                    print("[FATAL] 화면 복구 실패 → ALL 진행을 중단합니다 "
                          f"(완료 {idx}/{total})")
                    break
                need_enter = True
                prev_step = None
            print(f"{result_mark} [{idx}/{total}] {label} {result_text}   "
                  f"{_now_hms()} (소요 {_elapsed_text(time.time() - started_at)})")
            print(SEPARATOR)
            if is_all and idx < total:
                wait_sec = 5 if need_enter else 2
                print(f"[ALL] 다음 항목 시작까지 {wait_sec}초 대기...")
                time.sleep(wait_sec)

    elif btn_name == "pushButton_7":
        # 7-2) MEW content validation
        check_wittimew(width, height, title_name)

    print("============================================== AutoTest completed ==============================================")
