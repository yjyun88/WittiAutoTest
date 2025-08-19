# utils.py
import sys
import os
import logging
from airtest.core.api import Template as _AT_Template

if getattr(sys, "frozen", False):
    RESOURCE_DIR = sys._MEIPASS                                # 읽기 전용 (번들 내부)
    OUTPUT_BASE  = os.path.dirname(sys.executable)             # 쓰기 전용 (exe 폴더)
else:
    RESOURCE_DIR = os.path.dirname(__file__)
    OUTPUT_BASE  = RESOURCE_DIR

logger = logging.getLogger(__name__)

def resource_path(rel_path: str) -> str:
    """리소스(읽기 전용) 절대 경로 반환"""
    return os.path.join(RESOURCE_DIR, rel_path.replace("\\", os.sep))

def output_path(*parts, is_file: bool = False) -> str:
    """
    OUTPUT_BASE 기준의 절대 경로 생성/반환.
    - 디렉터리 경로면 그 디렉터리 생성
    - 파일 경로면 부모 디렉터리만 생성
    """
    full = os.path.join(OUTPUT_BASE, *parts)
    looks_like_file = os.path.splitext(full)[1] != ""
    target_dir = os.path.dirname(full) if (is_file or looks_like_file) else full
    os.makedirs(target_dir, exist_ok=True)
    return full

class Template(_AT_Template):
    """Airtest Template 래퍼: 번들 내부 리소스 경로 자동 처리(읽기 전용)"""
    def __init__(self, tpl_path, *args, **kwargs):
        abs_path = resource_path(tpl_path)
        logger.debug(f"Template 로드: {tpl_path} → {abs_path}")
        if not os.path.isfile(abs_path):
            logger.error(f"파일 없음: {abs_path}")
        super().__init__(abs_path, *args, **kwargs)
