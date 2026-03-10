# utils.py
import logging
import os
import re
import sys

import cv2
import easyocr
import numpy as np
from airtest.core.api import Template as _AT_Template

if getattr(sys, "frozen", False):
    RESOURCE_DIR = sys._MEIPASS
    OUTPUT_BASE = os.path.dirname(sys.executable)
else:
    RESOURCE_DIR = os.path.dirname(__file__)
    OUTPUT_BASE = RESOURCE_DIR

logger = logging.getLogger(__name__)


def resource_path(rel_path: str) -> str:
    """Resolve template path from cwd first, then fallback to packaged/source resource dir."""
    norm_rel = rel_path.replace("\\", os.sep)

    # 1) Relative path at runtime (current working directory) first
    cwd_path = os.path.abspath(norm_rel)
    if os.path.isfile(cwd_path):
        return cwd_path

    # 2) Existing behavior fallback for bundled/source resources
    return os.path.join(RESOURCE_DIR, norm_rel)


def output_path(*parts, is_file: bool = False) -> str:
    """Build path under OUTPUT_BASE and create parent directories as needed."""
    full = os.path.join(OUTPUT_BASE, *parts)
    looks_like_file = os.path.splitext(full)[1] != ""
    target_dir = os.path.dirname(full) if (is_file or looks_like_file) else full
    os.makedirs(target_dir, exist_ok=True)
    return full


class Template(_AT_Template):
    """Airtest Template wrapper that resolves resource paths for source and bundled execution."""

    def __init__(self, tpl_path, *args, **kwargs):
        abs_path = resource_path(tpl_path)
        logger.debug(f"Template load: {tpl_path} -> {abs_path}")
        if not os.path.isfile(abs_path):
            logger.error(f"파일 없음: {abs_path}")
        super().__init__(abs_path, *args, **kwargs)


# ---------------------------------------------------------------------------
# Shared image / OCR utilities (consolidated from box_aram, box_mew, etc.)
# ---------------------------------------------------------------------------

_OCR_READER = None


def get_ocr_reader(langs=("ko", "en")):
    global _OCR_READER
    if _OCR_READER is not None:
        return _OCR_READER
    try:
        _OCR_READER = easyocr.Reader(list(langs), gpu=True)
    except Exception:
        _OCR_READER = easyocr.Reader(list(langs), gpu=False)
    return _OCR_READER


def norm_text(value):
    return re.sub(r"[^0-9A-Za-z가-힣]", "", str(value or "")).lower()


def load_bgr(path):
    if not os.path.isfile(path):
        return None
    data = np.fromfile(path, dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def resolve_roi_abs(img_w, img_h, roi_rel):
    x1r, y1r, x2r, y2r = roi_rel
    x1 = max(0, int(img_w * x1r))
    y1 = max(0, int(img_h * y1r))
    x2 = min(img_w - 1, int(img_w * x2r))
    y2 = min(img_h - 1, int(img_h * y2r))
    return x1, y1, x2, y2


def extract_text_hint(tpl_bgr):
    try:
        results = get_ocr_reader().readtext(tpl_bgr, detail=1)
    except Exception:
        return ""
    best_text = ""
    best_prob = -1.0
    for _bbox, text, prob in results:
        n = norm_text(text)
        if len(n) < 2:
            continue
        if float(prob) > best_prob:
            best_prob = float(prob)
            best_text = text
    return best_text


def roi_change_score(prev_bgr, curr_bgr):
    if prev_bgr is None or curr_bgr is None:
        return 100.0
    h = min(prev_bgr.shape[0], curr_bgr.shape[0])
    w = min(prev_bgr.shape[1], curr_bgr.shape[1])
    if h <= 0 or w <= 0:
        return 100.0
    a = cv2.cvtColor(prev_bgr[:h, :w], cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(curr_bgr[:h, :w], cv2.COLOR_BGR2GRAY)
    return float(np.mean(cv2.absdiff(a, b)))