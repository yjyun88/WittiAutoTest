# AutoTest.py
import os

from airtest.core.api import connect_device, device, time

from TEST_witti_box import check_wittibox
from TEST_witti_world import check_wittiaram, check_wittimew
from download_thumbnails import cleanup_thumbnails
from request_API import get_study_access_auth


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

    if btn_name == "pushButton_2":
        # 6) WittiBox content validation
        if not mem_id or not mem_nm:
            print("[ERROR] study/access memId/memNm is missing. Cannot run WittiBox test.")
            return
        ok = check_wittibox([mem_id], [mem_nm], authToken, server, inputId)
        if not ok:
            print("[ERROR] WittiBox test stopped due to class selection failure.")
            return

    elif btn_name == "pushButton_3":
        # 7-1) Arambook world content validation
        if subjCd == 0:
            # ALL: 한글(1) → 수학(2) → 창의(3) 순서로 실행
            subj_names = {1: "한글", 2: "수학", 3: "창의"}
            for subj in (1, 2, 3):
                print(f"====== [ALL] {subj_names[subj]} 과목 시작 ({subj}/3) ======")
                check_wittiaram(width, height, authToken, subj, itemCd, curtnSeq, server)
                print(f"====== [ALL] {subj_names[subj]} 과목 완료 ({subj}/3) ======")
                if subj < 3:
                    print("[ALL] 다음 과목 시작까지 5초 대기...")
                    time.sleep(5)
        else:
            check_wittiaram(width, height, authToken, subjCd, itemCd, curtnSeq, server)

    elif btn_name == "pushButton_7":
        # 7-2) MEW content validation
        check_wittimew(width, height, title_name)

    print("============================================== AutoTest completed ==============================================")
