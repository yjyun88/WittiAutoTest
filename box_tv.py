import os
import time as pytime

from airtest.core.api import device, sleep, touch, wait

from Touch_template import touch_template
from box_ACT import capture_screen
from check_video import is_video_playing
from create_report import create_report, input_excel, report_thumbnail_error
from utils import Template, output_path

BASE_RESOLUTION = (1920, 1200)
MAX_SWIPE_ATTEMPTS = 8
# 카드 한 칸(≈카드 간격)만큼만 민다. 1920px 기준 간격이 699px이라 0.36.
SWIPE_STEP_RATIO = 0.36
SWIPE_DURATION_MS = 1200


def swipe_one_card():
    """TV 목록을 카드 한 칸만큼 왼쪽으로 민다.

    airtest 의 swipe() 는 이 기기에서 벡터 길이도 duration 도 먹지 않는다.
    -0.2 든 -0.5 든, duration 을 3초로 늘려도 결과가 소수점까지 같았다.
    한 번에 목록 끝(최대 스크롤)까지 가버린다.

    그러면 목록 중간 카드는 어느 위치에서도 화면 경계에 걸쳐 잘린다.
    실측(1920x1200, 카드 간격 699px)으로 tvList_2 는

        처음    중심 x=1787  오른쪽이 잘려 왼쪽 69%만 노출
        스와이프 후 중심 x=133  왼쪽이 잘려 오른쪽 69%만 노출

    템플릿 전체가 들어가는 창이 없어 매칭 점수가 0.36 에서 오르지 않았고,
    MAX_SWIPE_ATTEMPTS 를 모두 소진하며 100초씩 태운 뒤 실패했다.

    adb 의 input swipe 는 끈 거리만큼만 정확히 움직인다. 같은 자리에서
    699px 을 끌면 tvList_2 가 중심 x=1016 에 온전히 들어오고 점수 0.96 이 나온다.
    """
    w, h = device().get_current_resolution()
    if h > w:
        w, h = h, w
    y = int(h * 0.6)
    x1 = int(w * 0.83)
    x2 = int(x1 - w * SWIPE_STEP_RATIO)
    device().shell(f"input swipe {x1} {y} {x2} {y} {SWIPE_DURATION_MS}")
    sleep(1.0)


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

    # 카테고리는 리스트 진입 시 1회만 터치 (컨텐츠 종료 시 리스트 위치가 초기화됨)
    if before_template:
        touch_template(before_template, region_code=7)

    for img_file in tvlist_images:
        img_path = os.path.join(image_folder_abs, img_file)
        started_at = pytime.perf_counter()
        try:
            attempts = 0
            touched = False
            while not touched and attempts < MAX_SWIPE_ATTEMPTS:
                if touch_template(Template(img_path)):
                    touched = True
                else:
                    print(f"'{img_file}' 이미지 터치 실패. 스와이프 후 재시도합니다. ({attempts + 1}/{MAX_SWIPE_ATTEMPTS})")
                    swipe_one_card()
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
