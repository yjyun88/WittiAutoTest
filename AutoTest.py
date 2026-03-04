# AutoTest.py

from airtest.core.api import connect_device, device, time

from TEST_witti_box import check_wittibox
from TEST_witti_world import check_wittiaram, check_wittimew
from download_thumbnails import cleanup_thumbnails
from request_API import get_study_access_auth


def AutoTest_Start(
    btn_name,
    device_name,
    inputId,
    inputPwd,
    subjCd,
    itemCd,
    curtnSeq,
    title_name,
    server,
    study_access_auth_token=None,
):
    # 0) Connect device
    connect_device(f"Android://127.0.0.1:5037/{device_name}?cap_method=MINICAP")

    # 1) Read current device resolution
    width, height = device().get_current_resolution()
    if height > width:
        width, height = height, width
    print(f"Current device resolution: {width} x {height}")

    print("Current server:", server)
    match server:
        case "Prod":
            server = "api"
        case "QA":
            server = "qa-api"
        case "Dev":
            server = "dev-api"
        case "Total-Test":
            server = "total-test-api"

    # 4) Use memNm, memId and authToken saved by study/access
    mem_nm, mem_id, saved_auth_token = get_study_access_auth()
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
        check_wittibox([mem_id], [mem_nm], authToken, server)

    elif btn_name == "pushButton_3":
        # 7-1) Arambook world content validation
        check_wittiaram(width, height, authToken, subjCd, itemCd, curtnSeq, server)

    elif btn_name == "pushButton_7":
        # 7-2) MEW content validation
        check_wittimew(width, height, title_name)

    # Final cleanup
    cleanup_thumbnails()
    time.sleep(1)

    print("============================================== AutoTest completed ==============================================")
