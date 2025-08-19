import sys, time, os

from Touch_template import touch_template
from utils import Template, output_path
from airtest.core.api import exists
from box_ACT import capture_screen
from create_report import create_report, input_excel
from check_video import is_video_playing

before_tpl = Template(r"button_images\aram_cate.png")
after_tpl = [
    Template(r"button_images\aram_exit.png", threshold=0.85),
    Template(r"button_images\exit_y.png"),
]
aram_play = Template(r"button_images\aram_play.png", threshold=0.9)


# 아람 커리큘럼 선택
def touch_aramlist_images(
    childNm,
    image_folder="downloaded_images",
    before_template=before_tpl,    # 사전 터치 (카테고리 선택)
    after_templates=after_tpl,    # 사후 터치 (컨텐츠 종료)
):
    """
    downloaded_images 폴더 내 aramList 썸네일 이미지를 순서대로 터치
    : image_folder: 이미지가 저장된 폴더 경로(기본값 "downloaded_images")
    : before_template: 터치 전 항상 먼저 터치할 Template(예: 리스트 진입용)
    : after_templates: 각 썸네일 터치 후 추가로 터치할 Template들의 리스트
    : time.sleep(n): 터치 후 대기 시간(n초)
    """
    image_folder_abs = output_path(image_folder)

    # 1. aramList 이미지 파일만 선별
    aramlist_images = sorted([
        f for f in os.listdir(image_folder_abs)
        if childNm in f
        and "aramList" in f
        and f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))
    ])

    print(f"총 {len(aramlist_images)}개의 aramList 이미지를 터치 시도합니다.")

    # 2. 각 이미지를 화면에서 찾아 터치
    for img_file in aramlist_images:
        img_path = os.path.join(image_folder_abs, img_file)
        try:
            # 1) 카테고리 리스트 터치
            if before_template:
                touch_template(before_template)
                time.sleep(1)

            max_swipe_attempts = 5 # 최대 스와이프 재시도 횟수
            attempts = 0
            touched = False

            while not touched and attempts < max_swipe_attempts:
                try:
                    touch_template(Template(img_path))
                    touched = True # 이미지를 찾아서 터치 성공
                except Exception as e:
                    print(f"'{img_file}' 이미지 터치 실패: {e}. 리스트를 스와이프하고 재시도합니다. (시도 {attempts + 1}/{max_swipe_attempts}회)")
                    swipe((0.5, 0.6), vector=[-0.5, 0]) # 왼쪽으로 스와이프
                    time.sleep(1) # 스와이프 후 잠시 대기
                    attempts += 1
            # 최대 시도 횟수 후에도 이미지를 찾지 못한 경우
            if not touched:
                print(f"경고: 최대 스와이프 시도({max_swipe_attempts}회) 후에도 '{img_file}' 이미지를 찾지 못했습니다.")

            print("======================================== 컨텐츠 실행 대기 ========================================")
            time.sleep(30)

            # 1-1) 컨텐츠 화면에 play 버튼 있으면 버튼 누르기
            if exists(aram_play):
                touch_template(aram_play)

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
                for tpl in after_templates:
                    touch_template(tpl)
                    time.sleep(3)
        except Exception as e:
            print(f"{img_file} 이미지를 못 찾았거나 터치 실패: {e}")
            sys.exit(1)
