#AutoTest.py

from airtest.core.api import device, time, connect_device

from TEST_witti_box import check_wittibox
from TEST_witti_world import check_wittiaram, check_wittimew
from request_API import login_step1, login_step2
from download_thumbnails import cleanup_thumbnails


def AutoTest_Start(
        btn_name,
        device_name,
        inputId,
        inputPwd,
        subjCd,
        itemCd,
        curtnSeq,
        title_name,
        server
):

#======================================================================================================
    # 0) 디바이스 연결

    connect_device(f"Android://127.0.0.1:5037/{device_name}?cap_method=MINICAP")

#======================================================================================================

    
    """ 
        NBOM001 / dlrtks1122@@
        MGguest001 ~ MGguest015 / mini1122@@
        IKSAN0001 ~ IKSAN0020, IKSAN0060, IKSAN0080, IKSAN0100 / dlrtks1122@@ (Dev는 1111)
        solmips0001~0012 / solmips1122@@
        smps001~020 / smps1122@@
        jinchun001~032 / jinchun1122@@

        학습 리포트용 : reporttest01~05 / mini1122@@
    """

   # 2) 현재 연결된 디바이스 해상도 가져오기 (width, height)
    width, height = device().get_current_resolution()
    if height > width:
        width, height = height, width
    print(f"현재 디바이스 해상도 : {width} * {height}")

    print("현재 서버 선택 상태 : ", server)
    match server:
        case "Prod":
            server = "api"
        case "QA":
            server = "qa-api"
        case "Dev":
            server = "dev-api"
        case "Total-Test":
            server = "total-test-api"

    # 3) 1차 로그인 : 통합 로그인 API 호출 (refreshToken, childIds)
    refreshToken, childIds, childNms = login_step1(inputId, inputPwd, server)
    print("로그인 STEP1 → refreshToken:", refreshToken)
    print("로그인 STEP1 → childIds:", childIds)
    print("로그인 STEP1 → childNms:", childNms)


    # 4) 2차 로그인 : 이슈 토큰 발급 API 호출 (authToken)
    authToken = login_step2(refreshToken, childIds, server)
    print("로그인 STEP2 → authToken:", authToken)


    # 5) 이미지 다운로드 폴더 정리 : \downloaded_images
    cleanup_thumbnails()
    time.sleep(1)

    if btn_name == "pushButton_2":
        # 6) 런처 컨텐츠 검증 실행
        check_wittibox(childIds, childNms, authToken, server)

     
    elif btn_name == "pushButton_3":
        # 7-1) 월드 > 스쿨 > 아람북월드 컨텐츠 검증
        check_wittiaram(width, height, authToken, subjCd, itemCd, curtnSeq, server)

    elif btn_name == "pushButton_7":
        # 7-2 월드 > 스쿨 > MEW 컨텐츠 검증
        check_wittimew(width, height, title_name)


    # 6) 이미지 다운로드 폴더 정리 : \downloaded_images
    cleanup_thumbnails()
    time.sleep(1)


    # 컨텐츠 검증 종료
    print("============================================== AutoTest 수행 완료 ==============================================")

