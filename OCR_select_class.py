import os
import re
from difflib import SequenceMatcher

import cv2
import easyocr
from airtest.core.api import device, sleep, touch

_READER = None
DEBUG_DIR = "debug_images"
os.makedirs(DEBUG_DIR, exist_ok=True)

# Default class list area (relative to screen): x1, y1, x2, y2
DEFAULT_ROI_REL = (0.2917, 0.3833, 0.5000, 0.7583)
CLASS_TEXT_ALIAS = {
    "텔": "벨",
    "델": "벨",
    "벌": "벨",
    "캘": "벨",
    "플": "클",
}
CLASS_PREFIX = "레벨"
SPRING_CLASS = "늘봄"
FULL_SCREEN_ROI = "full"
DEFAULT_ROI = "default"


def _get_reader():
    global _READER
    if _READER is not None:
        return _READER
    try:
        _READER = easyocr.Reader(["ko"], gpu=True)
    except Exception:
        _READER = easyocr.Reader(["ko"], gpu=False)
    return _READER


def _normalize_text(value):
    return re.sub(r"[^0-9A-Za-z가-힣]", "", str(value or "")).lower()


def _normalize_class_text(value):
    text = str(value or "")
    text = re.sub(r"\s+", "", text)
    for wrong, correct in CLASS_TEXT_ALIAS.items():
        text = text.replace(wrong, correct)
    text = _normalize_text(text)
    if re.match(r"^레[^0-9]*\d+$", text):
        digit = re.search(r"\d+", text)
        text = f"{CLASS_PREFIX}{digit.group(0)}"
    return text


def _is_class_target(target_text):
    target_norm = _normalize_class_text(target_text)
    return bool(re.match(rf"^{CLASS_PREFIX}\d+$", target_norm) or target_norm == SPRING_CLASS)


def _resolve_roi(roi, img_w, img_h):
    if roi == DEFAULT_ROI:
        x1r, y1r, x2r, y2r = DEFAULT_ROI_REL
        return (
            int(x1r * img_w),
            int(y1r * img_h),
            int(x2r * img_w),
            int(y2r * img_h),
        )
    if roi is None or roi == FULL_SCREEN_ROI:
        return (0, 0, img_w, img_h)
    x1, y1, x2, y2 = roi
    return (
        max(0, int(x1)),
        max(0, int(y1)),
        min(img_w, int(x2)),
        min(img_h, int(y2)),
    )


def _bbox_center(bbox):
    xs = [pt[0] for pt in bbox]
    ys = [pt[1] for pt in bbox]
    return float(sum(xs) / 4.0), float(sum(ys) / 4.0)


def _build_variants(crop_bgr, is_class_target=False):
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=1.6, fy=1.6, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    eq = clahe.apply(gray)
    blur = cv2.GaussianBlur(eq, (3, 3), 0)
    sharpen = cv2.addWeighted(eq, 1.5, blur, -0.5, 0)
    _, th_inv = cv2.threshold(sharpen, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _, th = cv2.threshold(sharpen, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    adaptive = cv2.adaptiveThreshold(
        sharpen, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    variant_scale = 1.6
    if is_class_target:
        return [
            (cv2.cvtColor(sharpen, cv2.COLOR_GRAY2RGB), variant_scale),
            (cv2.cvtColor(th_inv, cv2.COLOR_GRAY2RGB), variant_scale),
            (cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB), variant_scale),
        ]
    return [
        (cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB), variant_scale),
        (cv2.cvtColor(sharpen, cv2.COLOR_GRAY2RGB), variant_scale),
        (cv2.cvtColor(th_inv, cv2.COLOR_GRAY2RGB), variant_scale),
        (cv2.cvtColor(th, cv2.COLOR_GRAY2RGB), variant_scale),
        (cv2.cvtColor(adaptive, cv2.COLOR_GRAY2RGB), variant_scale),
    ]


def _calc_similarity(text_norm, target_norm):
    if not text_norm or not target_norm:
        return 0.0
    return SequenceMatcher(None, text_norm, target_norm).ratio()


def _candidate_metrics(text, target_text):
    if _is_class_target(target_text):
        text_norm = _normalize_class_text(text)
        target_norm = _normalize_class_text(target_text)
    else:
        text_norm = _normalize_text(text)
        target_norm = _normalize_text(target_text)

    sim = _calc_similarity(text_norm, target_norm)
    contains = target_norm in text_norm or text_norm in target_norm
    text_digits = "".join(ch for ch in text_norm if ch.isdigit())
    target_digits = "".join(ch for ch in target_norm if ch.isdigit())
    digit_match = bool(target_digits) and text_digits == target_digits
    prefix_match = False
    if target_norm == SPRING_CLASS:
        prefix_match = text_norm == SPRING_CLASS
    elif target_norm.startswith(CLASS_PREFIX):
        prefix_match = text_norm.startswith(CLASS_PREFIX)

    return {
        "text_norm": text_norm,
        "target_norm": target_norm,
        "sim": sim,
        "contains": contains,
        "digit_match": digit_match,
        "prefix_match": prefix_match,
    }


def _score_candidate(metrics, prob):
    score = (metrics["sim"] * 0.72) + (max(0.0, float(prob)) * 0.13)
    if metrics["digit_match"]:
        score += 0.10
    if metrics["prefix_match"]:
        score += 0.05
    return score


def _is_pass_candidate(metrics, prob, min_prob):
    if metrics["target_norm"] == SPRING_CLASS:
        return metrics["text_norm"] == SPRING_CLASS and float(prob) >= 0.20
    if metrics["target_norm"].startswith(CLASS_PREFIX):
        if metrics["prefix_match"] and metrics["digit_match"] and metrics["sim"] >= 0.45:
            return True
        if metrics["contains"] and metrics["digit_match"]:
            return True
        return False
    return (float(prob) >= min_prob and metrics["sim"] >= 0.60) or (
        metrics["contains"] and metrics["sim"] >= 0.45
    )


def _pick_best_candidate(results, target_text, min_prob):
    best = None
    for bbox, text, prob in results:
        metrics = _candidate_metrics(text, target_text)
        if not metrics["text_norm"]:
            continue
        if not _is_pass_candidate(metrics, prob, min_prob):
            continue
        cand = {
            "bbox": bbox,
            "text": text,
            "prob": float(prob),
            "sim": metrics["sim"],
            "score": _score_candidate(metrics, prob),
        }
        if best is None or cand["score"] > best["score"]:
            best = cand
    return best


def find_text(target_text, conf_threshold=40, scale=1.3, roi=DEFAULT_ROI, max_variants=None, log_fail=True):
    is_class_target = _is_class_target(target_text)
    target_norm = _normalize_class_text(target_text) if is_class_target else _normalize_text(target_text)
    if not target_norm:
        print(f"[find_text] target='{target_text}' invalid target_norm")
        return None

    img_bgr = device().snapshot()
    img_h, img_w = img_bgr.shape[:2]
    x1, y1, x2, y2 = _resolve_roi(roi, img_w, img_h)
    if x2 <= x1 or y2 <= y1:
        print(f"[find_text] target='{target_text}' invalid roi={(x1, y1, x2, y2)}")
        return None

    crop = img_bgr[y1:y2, x1:x2]
    scaled = cv2.resize(
        crop,
        (max(1, int(crop.shape[1] * scale)), max(1, int(crop.shape[0] * scale))),
        interpolation=cv2.INTER_CUBIC,
    )

    reader = _get_reader()
    min_prob = max(0.0, min(float(conf_threshold) / 100.0, 1.0))
    best = None
    best_score_seen = -1.0
    best_variant_scale = 1.0
    variants = _build_variants(scaled, is_class_target=is_class_target)
    if max_variants is not None:
        variants = variants[: max(1, int(max_variants))]

    for variant, variant_scale in variants:
        results = reader.readtext(variant, detail=1)
        for _bbox, _text, _prob in results:
            metrics = _candidate_metrics(_text, target_text)
            if not metrics["text_norm"]:
                continue
            score = _score_candidate(metrics, _prob)
            if score > best_score_seen:
                best_score_seen = score
        cand = _pick_best_candidate(results, target_text, min_prob)
        if cand is not None and (best is None or cand["score"] > best["score"]):
            best = cand
            best_variant_scale = variant_scale
        if best is not None and best["score"] >= 0.88:
            break

    if best is None:
        if log_fail:
            print(
                f"[find_text] FAIL target='{target_text}' "
                f"best_score={best_score_seen:.3f} conf_threshold={conf_threshold} "
                f"roi={(x1, y1, x2, y2)}"
            )
        return None

    cx_scaled, cy_scaled = _bbox_center(best["bbox"])
    total_scale = scale * best_variant_scale
    cx = x1 + (cx_scaled / total_scale)
    cy = y1 + (cy_scaled / total_scale)
    return {
        "x": cx,
        "y": cy,
        "text": best["text"],
        "prob": best["prob"],
        "sim": best["sim"],
        "score": best["score"],
        "roi": (x1, y1, x2, y2),
    }


def select_class(childNm, conf_threshold=40, delay=1.0, scale=1.3, roi=DEFAULT_ROI, max_variants=None, log_fail=True):
    """
    Find target text using OCR and touch the best-matched result.
    Returns True on success, False on failure.
    """
    found = find_text(
        childNm,
        conf_threshold=conf_threshold,
        scale=scale,
        roi=roi,
        max_variants=max_variants,
        log_fail=log_fail,
    )
    if not found:
        print(f"[select_class] no match: '{childNm}'")
        return False

    debug = device().snapshot()
    x1, y1, x2, y2 = found["roi"]
    cv2.rectangle(debug, (x1, y1), (x2, y2), (255, 255, 0), 2)
    cv2.circle(debug, (int(found["x"]), int(found["y"])), 8, (0, 0, 255), -1)
    cv2.imwrite(os.path.join(DEBUG_DIR, "select_class_last.png"), debug)

    print(
        f"[select_class] hit='{found['text']}' sim={found['sim']:.2f} "
        f"conf={found['prob']*100:.1f}% score={found['score']:.3f}"
    )
    try:
        touch((found["x"], found["y"]))
        sleep(delay)
        return True
    except Exception as e:
        print(f"[select_class] touch failed: {e}")
        return False
