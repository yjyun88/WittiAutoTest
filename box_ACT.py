import cv2

from airtest.core.api import *
from Touch_template import touch_template
from utils import Template
from PIL import Image
from datetime import datetime

from OCR_select_class import select_class

BASE_RESOLUTION = (1920, 1200)
attendance_tpl = Template(r"button_images\attendance_ok.png", resolution=BASE_RESOLUTION)

# 설정 > 클래스 선택
def class_select(childNm):
    #w, h = device().get_current_resolution()
    setup_tpl = Template(
            "button_images/setup_menu.png",  # 이미지 파일 경로
            resolution=BASE_RESOLUTION
        )
    back_tpl = Template(
            "button_images/setup_back.png",  # 이미지 파일 경로
            resolution=BASE_RESOLUTION
        )
        
    # 설정 진입
    touch_template(setup_tpl, region_code=6)
    print("설정 버튼 선택")
    sleep(2)
    
    # 클래스 선택
    print("클래스 선택 : ", childNm)
    select_class(childNm)
    sleep(2)

    # 대시보드로 이동(뒤로가기)
    touch_template(back_tpl)
    print("뒤로가기 버튼 선택")
    sleep(2)

    if exists(attendance_tpl):
        touch_template(attendance_tpl)


# 현재 디바이스 화면을 캡처하여 분류별/날짜별 폴더에 저장
def capture_screen(img_path, childNm, save_dir="screen_captures"):
    """
    : img_path: 원본 이미지 파일 경로
    : save_dir: root 스크린샷 저장 폴더 (기본 "screen_captures")
    : return: save_path (저장된 이미지 파일 경로)
    """
    try:
        if img_path:
            # 1) 카테고리 결정
            #base = os.path.basename(img_path)
            filename = os.path.splitext(os.path.basename(img_path))[0]
            if filename.startswith(f"{childNm}_"):
                base = filename[len(childNm) + 1:]
            else:
                base = filename

        # 2) 날짜별 하위 폴더 생성 (YYYYMMDD)
        date_folder = datetime.now().strftime("%Y%m%d")
        date_dir = os.path.join(save_dir, date_folder)
        os.makedirs(date_dir, exist_ok=True)

        # 3) 스크린샷 캡처
        img_cv = device().snapshot()  # BGR numpy array

        # 4) 파일명: save_{원본파일명}
        fname = f"save_{childNm}_{base}.png"
        capture_path = os.path.join(date_dir, fname)

        # 5) 파일로 저장 (PNG 형식)
        img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        pil_img.save(capture_path)
        print(f"[CAPTURE] 화면 저장됨 → {capture_path}")
        sleep(1)
        
        return capture_path, base

    except Exception as e:
        print("error : ", e)