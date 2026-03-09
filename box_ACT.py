import os
from datetime import datetime

import cv2
from PIL import Image
from airtest.core.api import *

from OCR_select_class import find_text
from Touch_template import touch_template
from utils import Template

BASE_RESOLUTION = (1920, 1200)
# attendance_tpl = Template(r"button_images\attendance_ok.png", resolution=BASE_RESOLUTION)


def _mean_diff(img_a, img_b):
    try:
        if img_a is None or img_b is None:
            return -1.0
        if img_a.shape != img_b.shape:
            img_b = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]))
        return float(cv2.absdiff(img_a, img_b).mean())
    except Exception:
        return -1.0


# \uc124\uc815 > \ud074\ub798\uc2a4 \uc120\ud0dd
def class_select(target_class_nm):
    setup_tpl = Template(
        "button_images/setup_menu.png",
        resolution=BASE_RESOLUTION,
    )

    opened = touch_template(
        setup_tpl,
        region_code=6,
        threshold=0.78,
        scale_min=0.70,
        scale_max=1.30,
        scale_step=0.02,
        quad_sub_ratio=0.40,
    )
    if not opened:
        print("[ERROR] setup menu button not found.")
        return False
    print("[class_select] setup menu open")
    sleep(2)

    class_setting_tpl = Template("button_images/class_setting.png", resolution=BASE_RESOLUTION)
    opened_class_setting = touch_template(
        class_setting_tpl,
        region_code=2,
        threshold=0.65,
        scale_min=0.70,
        scale_max=1.30,
        scale_step=0.02,
    )
    if not opened_class_setting:
        print("[ERROR] class setting button not found.")
        return False
    print("[class_select] class setting open")
    sleep(2)

    img_cv = device().snapshot()
    h, w = img_cv.shape[:2]
    left_roi = (0, 0, int(w * 0.25), h)
    print("[class_select] target class:", target_class_nm)

    found_class = find_text(
        target_class_nm,
        conf_threshold=40,
        scale=1.0,
        roi=left_roi,
        max_variants=2,
        log_fail=False,
    )
    if found_class:
        print(
            f"[class_select] class already selected: {found_class['text']} "
            f"(score={found_class.get('score', 0):.3f}) -> BACK"
        )
        keyevent("BACK")
        sleep(2)
        return True
    print(f"[class_select] target not currently selected: {target_class_nm}")

    class_change_text = "\ud074\ub798\uc2a4 \ubcc0\uacbd"
    found_change = find_text(
        class_change_text,
        conf_threshold=35,
        scale=1.0,
        roi=left_roi,
        max_variants=2,
    )
    if not found_change:
        print("[WARN] classNm not matched and class change text not found.")
        return False

    print(
        f"[class_select] class change text found: {found_change['text']} "
        f"(score={found_change.get('score', 0):.3f})"
    )
    before_change_tap = device().snapshot()
    print(
        f"[class_select] tapping class change text at "
        f"({int(found_change['x'])}, {int(found_change['y'])})"
    )
    touch((found_change["x"], found_change["y"]))
    sleep(1)
    after_change_tap = device().snapshot()
    print(f"[class_select] post-tap screen diff={_mean_diff(before_change_tap, after_change_tap):.2f}")

    target_pick = find_text(
        target_class_nm,
        conf_threshold=35,
        scale=1.0,
        roi=None,
        max_variants=2,
    )
    if not target_pick:
        print(f"[WARN] target class text not found after class-change screen: {target_class_nm}")
        return False
    print(
        f"[class_select] target class item found: {target_pick['text']} "
        f"(score={target_pick.get('score', 0):.3f})"
    )
    touch((target_pick["x"], target_pick["y"]))
    sleep(1)

    for img in (r"button_images\change_class_1.png", r"button_images\change_class_2.png"):
        try:
            ok = touch_template(Template(img))
            if not ok:
                print(f"[WARN] change button template not found: {img}")
                return False
        except Exception as e:
            print(f"[WARN] change button touch failed: {img}, error={e}")
            return False
        sleep(1)

    return True


def capture_screen(img_path, childNm, save_dir="screen_captures"):
    """
    : img_path: \uc6d0\ubcf8 \uc774\ubbf8\uc9c0 \ud30c\uc77c \uacbd\ub85c
    : save_dir: root \uc2a4\ud06c\ub9b0\uc0f7 \uc800\uc7a5 \ud3f4\ub354 (\uae30\ubcf8 "screen_captures")
    : return: save_path (\uc800\uc7a5\ud55c \uc774\ubbf8\uc9c0 \ud30c\uc77c \uacbd\ub85c)
    """
    try:
        base = "capture"
        if img_path:
            filename = os.path.splitext(os.path.basename(img_path))[0]
            if filename.startswith(f"{childNm}_"):
                base = filename[len(childNm) + 1:]
            else:
                base = filename
            if "--" in base:
                base = base.split("--", 1)[0]

        date_folder = datetime.now().strftime("%Y%m%d")
        date_dir = os.path.join(save_dir, date_folder)
        os.makedirs(date_dir, exist_ok=True)

        img_cv = device().snapshot()
        fname = f"save_{childNm}_{base}.png"
        capture_path = os.path.join(date_dir, fname)

        img_rgb = cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        pil_img.save(capture_path)
        print(f"[CAPTURE] \ud654\uba74 \uc800\uc7a5\ub428 -> {capture_path}")
        sleep(1)

        return capture_path, base

    except Exception as e:
        print("error : ", e)
