import os
import time as pytime

from airtest.core.api import sleep, wait

from Touch_template import touch_template
from box_ACT import capture_screen
from check_video import is_video_playing
from create_report import create_report, input_excel
from utils import Template, output_path

BASE_RESOLUTION = (1920, 1200)

before_tpl = Template(r"button_images\book_cate.png", resolution=BASE_RESOLUTION)
after_tpl_1 = Template(r"button_images\book_exit.png", threshold=0.6, resolution=BASE_RESOLUTION)
after_tpl_1_1 = Template(r"button_images\book_exit_t.png", threshold=0.6, resolution=BASE_RESOLUTION)
after_tpl_2 = Template(r"button_images\exit_y.png", threshold=0.85, resolution=BASE_RESOLUTION)


def _report_thumbnail_error(img_path, child_nm, image_folder_abs, message, started_at):
    capture_path, base = capture_screen(img_path, child_nm)
    file_path, wb, ws = create_report()
    thumb_path = os.path.join(image_folder_abs, os.path.basename(img_path))
    input_excel(
        "ERROR",
        child_nm,
        base,
        file_path,
        wb,
        ws,
        capture_path,
        thumb_path,
        error_message=message,
        duration_sec=round(pytime.perf_counter() - started_at, 2),
    )


def touch_booklist_images(
    childNm,
    image_folder="downloaded_images",
    before_template=before_tpl,
):
    image_folder_abs = output_path(image_folder)
    print("img_path : ", image_folder_abs)

    booklist_images = sorted([
        f for f in os.listdir(image_folder_abs)
        if childNm in f
        and "bookList" in f
        and f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))
    ])

    print(f"총 {len(booklist_images)}개의 bookList 이미지를 터치 시도합니다.")

    for img_file in booklist_images:
        img_path = os.path.join(image_folder_abs, img_file)
        started_at = pytime.perf_counter()
        try:
            if before_template:
                touch_template(before_template, region_code=7)

            print(f"화면에서 {img_file} 이미지 터치 시도")
            touched = touch_template(Template(img_path))
            if not touched:
                _report_thumbnail_error(
                    img_path,
                    childNm,
                    image_folder_abs,
                    "thumbnail template not found",
                    started_at,
                )
                continue

            print("======================================== 콘텐츠 실행 대기 ========================================")
            wait(after_tpl_1, timeout=60)

            video_playing = is_video_playing(timeout=30, interval=0.1, diff_threshold=0.2)
            sleep(1)
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

            ok = touch_template(after_tpl_1, 6)
            if not ok:
                touch_template(after_tpl_1_1)

            wait(after_tpl_2)
            touch_template(after_tpl_2, 0)
        except Exception as e:
            print(f"{img_file} 이미지 처리 실패: {e}")
            return False

    return True
