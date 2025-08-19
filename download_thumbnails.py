import os
import requests
import shutil
import stat

from urllib.parse import *
from utils import output_path


# 카테고리별 키 매핑
CONTENTCD_KEYS = {
    "bookList": "bookCd",
    "aramList": "aramCd",
    "tvList":   "tvCd",
    "mewList":  "mewCd",
    "missionList": "comCd",   # 미션 자체 코드(필요하면 사용)
}
CONTENTID_KEYS = {
    "mewList": "contsId",     # mew만 contentId 키가 다름
    "default": "contentId",
}

BASE_LISTS = ["bookList", "aramList", "tvList", "mewList"]  # 최종 목적지

def detect_target_list(item: dict) -> str:
    """
    missionList 항목의 실제 컨텐츠 종류를 추론.
    우선순위: 존재하는 코드 키 → 타입 문자열 힌트
    """
    if "bookCd" in item: return "bookList"
    if "aramCd" in item: return "aramList"
    if "tvCd"   in item: return "tvList"
    if "mewCd"  in item: return "mewList"

    # 타입 문자열 힌트 (백엔드 스키마에 따라 다를 수 있음)
    hint = item.get("comTypeNm")
    if "도서관" in hint: return "bookList"
    if "아람어스" in hint: return "aramList"
    if "위티TV"   in hint: return "tvList"
    if "MEW"  in hint: return "mewList"

    return None  # 못 맞추면 None

def build_display_name(item: dict, target_list: str) -> str:
    if target_list == "mewList":
        mainName = item.get("mainName", "")
        subName  = item.get("subName", "")
        # 둘 중 존재하는 것만 이어붙이기
        parts = [p.strip() for p in (mainName, subName) if p and p.strip()]
        return " - ".join(parts)
    return item.get("name")

def get_contentCd(item: dict, target_list: str):
    key = CONTENTCD_KEYS.get(target_list)
    return item.get(key) if key else None

def get_contentId(item: dict, target_list: str):
    key = CONTENTID_KEYS.get(target_list, CONTENTID_KEYS["default"])
    return item.get(key)

def download_all_thumbnails(childNm, curriculum_data, server):
    # 프로젝트 상대 경로
    folder_abs = output_path("downloaded_images")
    os.makedirs(folder_abs, exist_ok=True)
    print(f"이미지는 여기 저장됨: {folder_abs}")

    SERVERS_WITH_MISSION_LIST = ["dev-api", "qa-api"]

    # 서버에 따라 missionList 포함 여부
    raw_lists = (["missionList"] if server in SERVERS_WITH_MISSION_LIST else []) + BASE_LISTS

    content_info = []
    # 카테고리별 공용 인덱스(파일명/리스트명에 사용)
    counters = {k: 0 for k in BASE_LISTS}

    for src_list in raw_lists:
        item_list = curriculum_data.get("result", {}).get(src_list, []) or []
        for item in item_list:
            url = item.get("thumbnailUrl")
            if not url:
                continue

            # missionList면 실제 목적 카테고리로 라우팅
            if src_list == "missionList":
                target_list = detect_target_list(item)
                if not target_list:
                    print(f"[WARN] mission 항목의 카테고리를 추론하지 못했습니다: {item.get('name')}")
                    continue
            else:
                target_list = src_list

            # 확장자 결정
            path = urlsplit(url).path
            ext = os.path.splitext(path)[1]
            if not ext or len(ext) > 5:
                ext = ".jpg"

            # 카테고리별 인덱스 사용
            idx = counters[target_list]

            save_fname = f"{childNm}_{target_list}_{idx}{ext}"
            save_path  = os.path.join(folder_abs, save_fname)
            print(f"저장 경로: {save_path}")

            try:
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                with open(save_path, "wb") as f:
                    f.write(resp.content)
                print(f"이미지 다운로드 완료: {save_path}")

                name = build_display_name(item, target_list)
                contentCd  = get_contentCd(item, target_list)
                contentId  = get_contentId(item, target_list)
                webviewUrl = item.get("webviewUrl")

                content_info.append({
                    "list":       f"{target_list}_{idx}",  # 목적 카테고리로 기록
                    "contentCd":  contentCd,
                    "name":       name,
                    "contentId":  contentId,
                    "webviewUrl": webviewUrl,
                })

                # 처리 성공 시에만 카운터 증가
                counters[target_list] += 1

            except Exception as e:
                print(f"다운로드 실패: {url}, 에러: {e}")

    return content_info


# 파일 읽기 전용 속성 제거
def remove_readonly(func, path, _):    
    os.chmod(path, stat.S_IWRITE)
    func(path)


# 경로 내 파일, 폴더 제거
def cleanup_thumbnails():
    """
    'downloaded_images'와 'screen_captures' 폴더 내부의 모든 파일 및 서브폴더를 삭제합니다.
    실제 실행 시 EXE 옆에 생성된 폴더를 비우며, 폴더가 없으면 새로 만듭니다.
    """
    target_dirs = ["downloaded_images", "screen_captures"]

    for d in target_dirs:
        # output_path()가 폴더가 없으면 생성해 주고, 절대 경로를 반환
        folder = output_path(d)

        # 폴더 안의 항목들을 순회하며 삭제
        for name in os.listdir(folder):
            file_path = os.path.join(folder, name)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.remove(file_path)
                    print(f"[파일 삭제 완료] {file_path}")
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path, onerror=remove_readonly)
                    print(f"[폴더 삭제 완료] {file_path}")
            except Exception as e:
                print(f"[ERROR] cleanup 실패: {file_path}: {e!r}")


# 위티월드 아람 컨텐츠 썸네일 다운로드
def download_thumbnails(
        act_items, 
        output_dir
        ):
    """
    act_items: list of dicts, each with keys "actTag" and "contsUrl"
    output_dir: directory where thumbnails will be saved
    Returns a list of file paths that were successfully downloaded.
    """
    os.makedirs(output_dir, exist_ok=True)
    saved_files = []

    for idx, item in enumerate(act_items, start=1):
        tag = item.get("actTag", f"item{idx}")
        url = item.get("contsThumbUrl")
        if not url:
            print(f"[WARN] No URL for {tag!r}, skipping")
            continue

        # 1) 안전한 파일명 만들기 (태그를 알파벳/숫자/언더바만 허용)
        safe_tag = "".join(c if c.isalnum() else "_" for c in tag)

        # 2) URL에서 확장자 추출 (.png, .jpg 등)
        path = urlparse(url).path
        basename = os.path.basename(unquote(path))
        _, ext = os.path.splitext(basename)
        if not ext:
            ext = ".jpg"

        # 3) 저장할 파일명 및 전체 경로
        filename = f"{idx:02d}_{safe_tag}{ext}"
        filepath = os.path.join(output_dir, filename)

        # 4) 다운로드 시도
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(resp.content)
            print(f"[OK] Saved thumbnail for {tag!r} → {filepath}")
            saved_files.append(filepath)
        except Exception as e:
            print(f"[ERROR] Failed to download {url!r}: {e}")

    return saved_files