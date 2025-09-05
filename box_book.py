import sys, time, os

from Touch_template import touch_template
from box_ACT import capture_screen
from utils import Template, output_path

from create_report import create_report, input_excel
from check_video import is_video_playing


before_tpl = Template(r"button_images\book_cate.png")
after_tpl_1 = Template(r"button_images\book_exit.png")
after_tpl_2 = Template(r"button_images\exit_y.png", threshold=0.85)

#도서관 커리큘럼 선택
def touch_booklist_images(
    childNm,
    image_folder="downloaded_images",
    before_template=before_tpl,    # 사전 터치 (카테고리 선택)
):
    """
    downloaded_images 폴더 내 bookList 썸네일 이미지를 순서대로 터치
    : image_folder: 이미지가 저장된 폴더 경로(기본값 "downloaded_images")
    : before_template: 터치 전 항상 먼저 터치할 Template(예: 리스트 진입용)
    : after_templates: 각 썸네일 터치 후 추가로 터치할 Template들의 리스트
    : time.sleep(n): 터치 후 대기 시간(n초)

    """    
    image_folder_abs = output_path(image_folder)
    print("img_path : ", image_folder_abs)

    # 1. bookList 이미지 파일만 선별
    booklist_images = sorted([
        f for f in os.listdir(image_folder_abs)
        if childNm in f
        and "bookList" in f 
        and f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))
    ])

    print(f"총 {len(booklist_images)}개의 bookList 이미지를 터치 시도합니다.")

    # 2. 각 이미지를 화면에서 찾아 터치
    for img_file in booklist_images:
        img_path = os.path.join(image_folder_abs, img_file)
        try:
            # 1) 카테고리 리스트 터치
            if before_template:
                touch_template(before_template, region_code=7)
                time.sleep(1)
            print(f"화면에서 {img_file} 이미지를 찾아 터치 시도")            
            touch_template(Template(img_path))
            print("======================================== 컨텐츠 실행 대기 ========================================")
            time.sleep(10)
            
            # 2) 컨텐츠 실행 확인
            video_playing = is_video_playing(timeout=30, interval=0.1, diff_threshold=0.2)  
            capture_path, base = capture_screen(img_path, childNm)
            
            # 3) 엑셀 Report 생성, 데이터 삽입    
            file_path, wb, ws = create_report()
            time.sleep(1)
            class_name = f"{childNm}"
            content_name = f"{base}"
            thumb_path = os.path.join(image_folder_abs, img_file)
            input_excel(
                video_playing, 
                class_name, 
                content_name,
                file_path, 
                wb, 
                ws, 
                capture_path,
                thumb_path
                )
            time.sleep(1)
          
            # 5) 컨텐츠 종료
            touch_template(after_tpl_1, 6)
            time.sleep(2)
            touch_template(after_tpl_2, 0)
            time.sleep(2)

        except Exception as e:
            print(f"{img_file} 이미지를 못 찾았거나 터치 실패: {e}")
            sys.exit(1)
