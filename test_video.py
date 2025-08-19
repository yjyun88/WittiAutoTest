import ffmpeg
import datetime
import subprocess
import re

from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager

import time

def is_video_playing_in_browser(url: str, timeout: float = 20.0) -> bool:
    """
    Selenium으로 페이지 로드 후 <video> 요소의 paused 상태로 재생 여부 판단.
    :url: 검사할 영상 URL
    :timeout: 최대 대기 시간(초)
    :return: 재생 중이면 True, 아니면 False
    """
    driver = webdriver.Chrome(ChromeDriverManager().install())  # ChromeDriver 경로가 PATH에 있어야 함
    driver.get(url)
    start = time.time()

    while time.time() - start < timeout:
        # JS로 비디오 재생 여부 조회 (paused가 False면 재생 중)
        playing = not driver.execute_script(
            "return document.querySelector('video').paused;")
        if playing:
            print("✅ 브라우저에서 재생 확인")
            driver.quit()
            return True
        time.sleep(0.5)

    print("⚠️ 지정 시간 내에 재생 미확인")
    driver.quit()
    return False


def get_web_video_duration_ffmpeg(url):
    try:
        # ffprobe를 사용하여 URL에서 직접 비디오 정보를 probe합니다.
        probe = ffmpeg.probe(url)
        duration_in_seconds = float(probe['format']['duration'])
        return datetime.timedelta(seconds=int(duration_in_seconds))
    except ffmpeg.Error as e:
        print(f"Error probing video from URL {url}: {e.stderr.decode()}")
        return None
    except KeyError:
        print(f"Error: Could not find 'duration' in video metadata for {url}.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

def get_audio_duration_ffmpeg(file_path_or_url):
    try:
        probe = ffmpeg.probe(file_path_or_url)
        # 오디오 스트림을 찾습니다.
        audio_stream = next((s for s in probe['streams'] if s['codec_type'] == 'audio'), None)

        if audio_stream and 'duration' in audio_stream:
            duration_in_seconds = float(audio_stream['duration'])
            return datetime.timedelta(seconds=int(duration_in_seconds))
        elif 'duration' in probe['format']: # 전체 파일 포맷 정보에 duration이 있을 수 있음
            duration_in_seconds = float(probe['format']['duration'])
            return datetime.timedelta(seconds=int(duration_in_seconds))
        else:
            return None
    except ffmpeg.Error as e:
        print(f"Error probing audio from {file_path_or_url}: {e.stderr.decode()}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None
    

def get_webview_audio_duration(device_id: str = None) -> float | None:
    cmd = ["adb"]
    if device_id:
        cmd += ["-s", device_id]
    cmd += ["shell", "dumpsys", "media_session"] # <-- 여기 변경

    try:
        raw = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode('utf-8', errors='ignore')
    except subprocess.CalledProcessError:
        return None

    # duration=123456 또는 duration: 123456 형태를 모두 찾을 수 있도록 정규표현식 수정
    # dumpsys media_session의 duration은 Metadata 섹션에 있을 가능성이 높음
    m = re.search(r"duration[=:]\s*(\d+)", raw, re.IGNORECASE)
    if m:
        ms = int(m.group(1))
        return ms / 1000.0  # 초 단위로 변환
    return None

