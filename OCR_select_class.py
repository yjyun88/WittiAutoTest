import os
import re

from airtest.core.api import device, touch, sleep
from PIL import Image, ImageFilter
from difflib import SequenceMatcher
import cv2
import numpy as np
import easyocr

#======================================================================================================

# 한글 OCR을 위한 EasyOCR Reader 초기화 (GPU 사용 원하면 gpu=True)
reader = easyocr.Reader(['ko'], gpu=True)

# 디버그 이미지 저장 폴더
DEBUG_DIR = "debug_images"
os.makedirs(DEBUG_DIR, exist_ok=True)

#======================================================================================================


# 설정 > 클래스 선택
def select_class(childNm, conf_threshold=40, delay=1.0, scale=1.5, roi=None):
    """
    단일 텍스트(childNm)를 전처리(배경제거→샤프닝) & EasyOCR로 인식 후 터치합니다.
    : childNm: 찾을 문자열
    : conf_threshold: OCR 신뢰도 기준 (0~100)
    : delay: 터치 후 대기 시간(초)
    : scale: 기준 스케일 배율 (baseline DPI=160 대비)
    : roi: (x1,y1,x2,y2) 튜플로 지정된 ROI (원본 좌표), None이면 전체 화면
    : return: True(성공) or False(실패)
    """
    # 1) 디바이스 DPI 및 해상도 정보
    out_dpi = device().shell("wm density")
    m = re.search(r"(\d+)", out_dpi)
    dpi = int(m.group(1)) if m else 160
    print("Device dpi 값 : ", dpi)

    # 1-1) 스냅샷 & 해상도 읽기
    img_cv = device().snapshot()
    img_h, img_w = img_cv.shape[:2]    
    print("Device 높이 값: ", img_h)
    print("Device 넓이 값 : ", img_w)

    # 2) 스케일 계산 및 제한
    actual_scale = min(scale * (dpi / 160), 1.2)
    print("actual_scale 값 : ", actual_scale)

    # 3) 화면 캡처 및 스케일링
    img_resized = cv2.resize(img_cv,
                             (int(img_w * actual_scale), int(img_h * actual_scale)),
                             interpolation=cv2.INTER_LANCZOS4)
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)

    # 4) ROI 상대 좌표 지정
    roi_rel = (0.2917, 0.3833, 0.5000, 0.7583)
    print("roi_rel 값 : ", roi_rel)

    # 4-1) 상대→절대 좌표 변환 함수
    def rel2abs(roi_rel, w, h):
        x1r, y1r, x2r, y2r = roi_rel
        return (
            int(x1r * w),  # x1
            int(y1r * h),  # y1
            int(x2r * w),  # x2
            int(y2r * h)   # y2
        )

    # 4-2) 실제 ROI 픽셀 좌표
    roi = rel2abs(roi_rel, img_w, img_h)

    # 4-3) 기존 ROI 크롭 로직에 roi 넘겨주기
    x1, y1, x2, y2 = roi
    sx1, sy1 = int(x1 * actual_scale), int(y1 * actual_scale)
    sx2, sy2 = int(x2 * actual_scale), int(y2 * actual_scale)
    crop = img_rgb[sy1:sy2, sx1:sx2]
    offset_x, offset_y = x1, y1

    # 5) 그레이스케일
    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    
    # 6) Blackhat 필터로 어두운 텍스트 강조 (light background에서 dark text 추출)
    bh_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (10, 10))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, bh_kernel)

    # 7) 대비 향상 (CLAHE)
    clahe = cv2.createCLAHE(clipLimit=1.0, tileGridSize=(16, 16))
    flat_eq = clahe.apply(blackhat)

    # 7-1) 대비 스트레칭 (0~255 전체 구간으로)
    flat_eq = cv2.normalize(flat_eq, None, 0, 255, cv2.NORM_MINMAX)
    flat_eq = cv2.GaussianBlur(flat_eq, (3,3), 0)
    
    # 8) 이진화 (반전+Otsu) → 글자는 하얗게, 배경은 검게
    _, thresh = cv2.threshold(
        flat_eq, 0, 255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    
    # 8-1) 모폴로지 팽창으로 획 굵기 보강
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1,1))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, close_kernel, iterations=1)
    thresh = cv2.dilate(closed, close_kernel, iterations=1)

    # 9) 샤프닝 (UnsharpMask) 후 배열 변환
    pil_th = Image.fromarray(thresh)
    sharp = pil_th.filter(ImageFilter.UnsharpMask(radius=1, percent=25, threshold=50))
    sharp_arr = np.array(sharp)

    # 10) 전처리된 이미지 저장 (디버깅용)
    pre_path = os.path.join(DEBUG_DIR, "ocr_preprocessed.png")
    full_res = cv2.resize(sharp_arr, (img_w, img_h), interpolation=cv2.INTER_LANCZOS4)
    Image.fromarray(full_res).save(pre_path, dpi=(dpi, dpi))

    # 11) EasyOCR 수행
    sharp_rgb = cv2.cvtColor(sharp_arr, cv2.COLOR_GRAY2RGB)
    results = reader.readtext(
        sharp_rgb, 
        detail=1
        )

    # 12) 결과 매칭 및 터치
    # 12-1) 신뢰도 조건 통과 후보만 모으기
    conf_cands = []
    for bbox, text, prob in results:
        sim = SequenceMatcher(None, text, childNm).ratio()
        print(f"  → 후보: '{text}', 신뢰도={prob*100:.1f}%, 유사도={sim:.2f}")
        if prob * 100 >= conf_threshold:
            conf_cands.append((bbox, text, prob, sim))

    # 12-2) 후보가 있으면 유사도 기준으로 최고값 선택
    if conf_cands:
        bbox, text, prob, sim = max(conf_cands, key=lambda x: x[3])
        print(f"[select_class] 선택된 텍스트(신뢰도 통과 중 최고 유사도): '{text}', 신뢰도={prob*100:.1f}%, 유사도={sim:.2f}")
    else:
        print(f"[select_class] 신뢰도 {conf_threshold}% 이상인 후보가 없습니다.")
        return False

    # 12-3) 터치 좌표 계산 & 실행
    xs = [pt[0] for pt in bbox]
    ys = [pt[1] for pt in bbox]
    avg_x, avg_y = sum(xs)/4, sum(ys)/4
    cx = avg_x / actual_scale + offset_x
    cy = avg_y / actual_scale + offset_y
    try:
        touch((cx, cy))
        sleep(delay)
        return True
    except Exception as e:
        print(f"[select_class] touch 실패: {e}")
        return False