import time

from box_aram import touch_aramlist_images
from box_book import touch_booklist_images
from download_thumbnails import *
from reques_API import *
from box_ACT import class_select
from box_mew import touch_mewlist_images
from box_tv import touch_tvlist_images


# 런처 컨텐츠 검증 실행
def check_wittibox(childIds, childNms, authToken, server):
    for idx, (childId, childNm) in enumerate(zip(childIds, childNms)):        
        try:
            # 클래스 선택
            class_select(childNm)            
            
            # 런처 커리큘럼 Data 가져오기 API 호출
            curriculum_data = get_curriculum_response(authToken, childId, server).json()
            
            # print(curriculum_data)
            print(f"=== childId[{idx}] = {childId} 커리큘럼 로드 ===")
            
            # 커리큘럼 썸네일 이미지 다운로드
            content_info = download_all_thumbnails(childNm, curriculum_data, server)
            #print("content_info : ", content_info)
            time.sleep(2)
            
            # 각 함수에 childNm 전달
            touch_booklist_images(childNm)
            time.sleep(2)
            touch_aramlist_images(childNm)
            time.sleep(2)
            touch_mewlist_images(childNm)
            time.sleep(2)
            touch_tvlist_images(childNm)
            time.sleep(2)
            
        except Exception as e:
            print(f"[WARN] {childNm} 처리 실패: {e!r}")
            continue