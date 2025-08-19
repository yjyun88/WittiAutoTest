import sys, time, os

from airtest.core.api import swipe, touch
from Touch_template import touch_template
from utils import Template, output_path

from box_ACT import capture_screen
from create_report import create_report, input_excel
from check_video import is_video_playing

before_tpl = Template(r"button_images\tv_cate.png")
after_tpl = [
    Template(r"button_images\tv_exit.png"),
    Template(r"button_images\exit_y.png")
]

def touch_tvlist_images(
    childNm,
    image_folder="downloaded_images",
    before_template=before_tpl,    # 사전 터치 (목록 진입 등)
    after_templates=after_tpl,    # 사후 터치 (닫기/확인 등)
):
    """
    downloaded_images 폴더 내 tvList 썸네일 이미지를 순서대로 터치
    : image_folder: 이미지가 저장된 폴더 경로(기본값 "downloaded_images")
    : before_template: 터치 전 항상 먼저 터치할 Template(예: 리스트 진입용)
    : after_templates: 각 썸네일 터치 후 추가로 터치할 Template들의 리스트
    : time.sleep(n): 터치 후 대기 시간(n초)
    """
    image_folder_abs = output_path(image_folder)

    # 1. tvList 이미지 파일만 선별
    tvlist_images = sorted([
        f for f in os.listdir(image_folder_abs)
        if childNm in f
        and "tvList" in f 
        and f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))
    ])

    print(f"총 {len(tvlist_images)}개의 tvList 이미지를 터치 시도합니다.")

    # 2. 각 이미지를 화면에서 찾아 터치
    for idx, img_file in enumerate(tvlist_images):
        img_path = os.path.join(image_folder_abs, img_file)
        try:
            # 1) 카테고리 리스트 터치
            if before_template:
                touch_template(before_template)
                time.sleep(1)
            # 1-1) 3번째 이후 순서일 경우 리스트 스와이프
            if idx > 2:
                print("리스트를 스와이프 합니다.")
                swipe((0.5, 0.6), vector=[-0.5, 0]) #화면 X좌표의 가운데(0.5), Y좌표의 가운데에서 밑으로 10프로(0.6), 왼쪽으로 50프로 만큼 스와이프(-5.0)
                time.sleep(1)
            print(f"화면에서 {img_file} 이미지를 찾아 터치 시도")
            touch_template(Template(img_path, threshold=0.91))
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

            # 4) 컨텐츠 종료
            if after_templates:
                #일시 정지를 위해 두번 터치
                touch((0.5, 0.5))
                time.sleep(1)
                touch((0.5, 0.5))
                time.sleep(1)
                for tpl in after_templates:
                    touch_template(tpl)
                    time.sleep(1)
        except Exception as e:
            print(f"{img_file} 이미지를 못 찾았거나 터치 실패: {e}")
            sys.exit(1)
