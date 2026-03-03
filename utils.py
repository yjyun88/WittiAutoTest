# utils.py
import logging
import os
import sys

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