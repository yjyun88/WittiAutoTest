import time
import numpy as np
import cv2
from airtest.core.api import device

def is_video_playing(timeout: float,
                     interval: float,
                     diff_threshold: float) -> str:
    """
    터치 후 비디오 재생 시작을 최대 timeout(초)만큼 기다리며 체크합니다.
    :timeout: 최대 대기 시간(초)
    :interval: 프레임 캡처 간격(초)
    :diff_threshold: 프레임 간 평균 픽셀 차이 임계값(0~255)
    :return: 재생 시작 확인 시 "PASS", 시간 초과 시 "FAIL"
    """
    start_time = time.time()
    prev = device().snapshot()
    prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)

    while True:
        elapsed = time.time() - start_time
        if elapsed >= timeout:
            print(f"⚠️ {timeout:.1f}s 내에 재생 시작 미확인, 비디오 재생 FAIL")
            return "FAIL"

        time.sleep(interval)
        curr = device().snapshot()
        curr_gray = cv2.cvtColor(curr, cv2.COLOR_BGR2GRAY)

        diff = cv2.absdiff(prev_gray, curr_gray)
        mean_diff = np.mean(diff)
        print(f"[DEBUG] 경과 {elapsed:.1f}s, mean_diff={mean_diff:.1f}")

        if mean_diff > diff_threshold:
            print(f"✅ 재생 시작 확인 (소요 {elapsed:.1f}s), 비디오 재생 PASS")
            return "PASS"

        prev_gray = curr_gray