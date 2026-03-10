import os
import time as pytime

from airtest.core.api import sleep, swipe, touch, wait

from Touch_template import touch_template
from box_ACT import capture_screen
from check_video import is_video_playing
from create_report import create_report, input_excel, report_thumbnail_error
from utils import Template, output_path

BASE_RESOLUTION = (1920, 1200)
MAX_SWIPE_ATTEMPTS = 8

before_tpl = Template(r"button_images\tv_cate.png", resolution=BASE_RESOLUTION)
after_tpl = [
    Template(r"button_images\tv_exit.png", resolution=BASE_RESOLUTION),
    Template(r"button_images\exit_y.png", resolution=BASE_RESOLUTION),
]



def touch_tvlist_images(
    childNm,
    image_folder="downloaded_images",
    before_template=before_tpl,
    after_templates=after_tpl,
):
    image_folder_abs = output_path(image_folder)

    tvlist_images = sorted([
        f for f in os.listdir(image_folder_abs)
        if childNm in f
        and "tvList" in f
        and f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))
    ])

    print(f"총 {len(tvlist_images)}개의 tvList 이미지를 터치 시도합니다.")

    for img_file in tvlist_images:
        img_path = os.path.join(image_folder_abs, img_file)
        started_at = pytime.perf_counter()
        try:
            if before_template:
                touch_template(before_template, region_code=7)

            attempts = 0
            touched = False
            while not touched and attempts < MAX_SWIPE_ATTEMPTS:
                if touch_template(Template(img_path)):
                    touched = True
                else:
                    print(f"'{img_file}' 이미지 터치 실패. 스와이프 후 재시도합니다. ({attempts + 1}/{MAX_SWIPE_ATTEMPTS})")
                    swipe((0.5, 0.6), vector=[-0.5, 0])
                    attempts += 1

            if not touched:
                report_thumbnail_error(
                    img_path,
                    childNm,
                    image_folder_abs,
                    "thumbnail template not found",
                    started_at,
                )
                continue

            print("======================================== 콘텐츠 실행 대기 ========================================")
            wait(Template(r"button_images\tv_exit.png"), timeout=60)
            sleep(3)

            video_playing = is_video_playing(timeout=30, interval=0.1, diff_threshold=0.2)
            capture_path, base = capture_screen(img_path, childNm)

            file_path, wb, ws = create_report()
            thumb_path = os.path.join(image_folder_abs, img_file)
            input_excel(
                video_playing,
                childNm,
                base,
                file_path,
                wb,
                ws,
                capture_path,
                thumb_path,
                duration_sec=round(pytime.perf_counter() - started_at, 2),
            )

            if after_templates:
                touch((0.5, 0.5))
                sleep(1)
                touch((0.5, 0.5))
                for tpl in after_templates:
                    touch_template(tpl)
        except Exception as e:
            print(f"{img_file} 이미지 처리 실패: {e}")
            return False

    return True
