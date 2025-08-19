import os
import sys
import time
import traceback

from datetime import datetime
from openpyxl import Workbook, load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from PIL import Image as PILImage
from openpyxl.styles import Border, Side
from io import BytesIO


# PNG 이미지를 optimize=True, compress_level 옵션으로 저장해 용량을 낮춤
def optimize_png(
        input_path, 
        output_path=None, 
        compress_level=9, 
        max_colors=128,
        max_width=200,
        max_height=200
    ):
    """
    : input_path: 원본 PNG 파일 경로
    : output_path: 최적화된 파일을 저장할 경로 (None 이면 덮어쓰기)
    : compress_level: 0(무압축)~9(최대압축) 레벨
    : return: 최적화된 파일 경로
    """
    if output_path is None:
        output_path = input_path

    # PNG 최적화 저장
    with PILImage.open(input_path) as img:
        # 리사이즈
        img.thumbnail((max_width, max_height), PILImage.LANCZOS)

        # 퀀타이즈 (팔레트 기반 색상 축소)
        img = img.convert("P", palette=PILImage.ADAPTIVE, colors=max_colors)
        # 저장
        img.save(
            output_path,
            format="PNG",
            optimize=True,
            compress_level=compress_level
        )
    print("이미지 최적화 완료")
    return output_path


# 워크시트 열 너비 설정
def adjust_column_widths(ws, padding=2, scale=1.3):
    """
    : ws: Worksheet 객체
    : padding: 문자열 길이에 더해줄 여유 문자 수 (기본 2)
    : scale: (max_len + padding)에 곱할 비율 (기본 1.2)
    """
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value is not None:
                length = len(str(cell.value))
                if length > max_len:
                    max_len = length

        # 폭 계산: (최대문자수 + 패딩) × 스케일
        new_width = (max_len + padding) * scale
        ws.column_dimensions[col_letter].width = new_width

        # 디버깅용
        print(f"→ 열 {col_letter} 너비 설정: {new_width:.1f} (chars)")


# 이미지 삽입 행 너비, 높이 설정
def adjust_row_heights(ws, row, px_size=200):
    """
    : ws: Worksheet 객체
    : row: 높이를 변경할 행 번호(1-based)
    : px_size: 픽셀 단위 크기 (기본 200px)
    """
    # 픽셀→포인트(pt) 및 픽셀→엑셀 열 너비(character) 배율
    PIXEL_TO_PT   = 72 / 96     # 1px ≈ 0.75pt
    PIXEL_TO_CHAR = 1 / 7       # 1 character ≈ 7px

    # 1) 헤더(1행)에서 'capture_screen' 열 인덱스 찾기
    header = next(ws.iter_rows(min_row=1, max_row=1))
    for cell in header:
        if cell.value == "capture_screen":
            cap_idx = cell.column
        elif cell.value == "content_thumb":
            thumb_idx = cell.column

    if cap_idx is None:
        raise ValueError("헤더에 'capture_screen' 열을 찾을 수 없습니다.")
    if thumb_idx is None:
        raise ValueError("헤더에 'content_thumb' 열을 찾을 수 없습니다.")

    # 2) 두 열 너비 설정 (px → character 단위)
    cap_letter   = get_column_letter(cap_idx)
    thumb_letter = get_column_letter(thumb_idx)

    cap_width   = px_size * PIXEL_TO_CHAR
    thumb_width = px_size * PIXEL_TO_CHAR

    ws.column_dimensions[cap_letter].width   = cap_width
    ws.column_dimensions[thumb_letter].width = thumb_width

    print(f"'capture_screen' 열({cap_letter}) 너비를 {cap_width:.1f} chars로 설정")
    print(f"'content_thumb' 열({thumb_letter}) 너비를 {thumb_width:.1f} chars로 설정")

    # 3) 지정된 행 높이 설정 (px → pt 단위)
    row_height_pt = px_size * PIXEL_TO_PT
    ws.row_dimensions[row].height = row_height_pt
    print(f"{row}행 높이를 {row_height_pt:.1f} pt로 설정")


# 엑셀에 결과 Data 삽입
def input_excel(
    video_playing,
    class_name, 
    content_name,
    file_path,
    wb,
    ws,
    capture_path,
    thumb_path,
    width=200,
    height=200,
    padding_chars=2
):
    """
    다음 행에
      - name 값을 'name' 열에 쓰고,
      - thumb_path 이미지를 'content_thumb' 열에 삽입하고,
      - capture_path 이미지를 'capture_screen' 열에 삽입하고,
      - video_playing 값을 'is_video_playing' 열에 입력합니다.
    """
    # 1) 헤더에서 열 번호 찾기
    header = next(ws.iter_rows(min_row=1, max_row=1))
    thumb_col = cap_col = video_col = None
    for cell in header:
        if cell.value == "class_name":
            class_col = cell.column
        elif cell.value == "content_name":
            content_col = cell.column
        elif cell.value == "content_thumb":
            thumb_col = cell.column
        elif cell.value == "capture_screen":
            cap_col = cell.column
        elif cell.value == "is_video_playing":
            video_col = cell.column

    if None in (class_col, content_col, thumb_col, cap_col, video_col):
        raise ValueError("헤더에 'class_name', 'content_name', 'content_thumb', 'capture_screen', 'is_video_playing' 중 하나를 찾을 수 없습니다.")

    # 2) 다음 빈 행
    row = ws.max_row + 1

    # 3) class_name, content_name 열에 입력
    class_cell_ref = f"{get_column_letter(class_col)}{row}"
    ws[class_cell_ref] = class_name
    ws[class_cell_ref].alignment = Alignment(vertical="center")

    content_cell_ref = f"{get_column_letter(content_col)}{row}"
    ws[content_cell_ref] = content_name
    ws[content_cell_ref].alignment = Alignment(vertical="center")

    # 4) content_thumb 열에 커리큘럼 썸네일 삽입
    if thumb_path:
        thumb_opt = optimize_png(thumb_path, compress_level=9)   # ← 이 줄 추가
        with open(thumb_opt, 'rb') as f:
            thumb_bytes = f.read()
        thumb_buf = BytesIO(thumb_bytes)
        thumb_img = XLImage(thumb_buf)
        thumb_img.width, thumb_img.height = width, height
        thumb_img._data = lambda imgb=thumb_bytes: imgb
        ws.add_image(thumb_img, f"{get_column_letter(thumb_col)}{row}")

    # 5) capture_screen 열에 화면 캡처 이미지 삽입
    cap_opt = optimize_png(capture_path, compress_level=9)   # ← 이 줄 추가
    with open(cap_opt, 'rb') as f:
        cap_bytes = f.read()
    cap_buf = BytesIO(cap_bytes)
    cap_img = XLImage(cap_buf)
    cap_img.width, cap_img.height = width, height
    cap_img._data = lambda imgb=cap_bytes: imgb
    ws.add_image(cap_img, f"{get_column_letter(cap_col)}{row}")

    # 6) is_video_playing 열에 video_playing 값 입력 및 스타일 적용
    res_col_letter = get_column_letter(video_col)
    res_cell_ref   = f"{res_col_letter}{row}"
    cell = ws[res_cell_ref]
    cell.value = video_playing
    cell.alignment = Alignment(vertical="center", horizontal="center")

    # 6-1) PASS: 초록색, 볼드 + 연한 초록 배경
    if video_playing == "PASS":
        cell.font = Font(color="008000", bold=True)  # 짙은 초록
        cell.fill = PatternFill(
            fill_type="solid",
            start_color="CCFFCC",  # 연한 녹색
            end_color="CCFFCC"
        )
    # 6-2) FAIL: 빨간색, 볼드 + 연한 빨간 배경
    elif video_playing == "FAIL":
        cell.font = Font(color="FF0000", bold=True)
        cell.fill = PatternFill(
            fill_type="solid",
            start_color="FFCCCC",  # 연한 빨간
            end_color="FFCCCC"
        )
    # 6-3) 그 외: 기본 폰트(볼드·색상·배경 모두 해제)
    else:
        cell.font = Font()  
        cell.fill = PatternFill(fill_type=None)

    # 7) 열 너비·행 높이 자동 조정
    adjust_column_widths(ws, padding=padding_chars)
    adjust_row_heights(ws, row)

    # 8) 테두리 적용 (값이 있는 모든 행에 얇은 테두리)
    apply_borders_to_filled_rows(ws)

    # 9) 저장
    try:
        wb.save(file_path)
        print(f"{row}행에 name='{class_name}', '{content_name}', thumb, capture, is_video_playing='{video_playing}' 삽입 완료")
    except Exception as e:
        print("=== 저장 중 예외 발생 ===")
        traceback.print_exc()   # 전체 스택트레이스 출력
        sys.exit(1)


# 워크시트에 실선 테두리 삽입
def apply_borders_to_filled_rows(ws):
    
    thin = Side(border_style="thin", color="000000")
    bd   = Border(top=thin, bottom=thin, left=thin, right=thin)

    for r in range(2, ws.max_row + 1):
        # 해당 행에 값이 하나라도 있으면 테두리 적용
        if any(ws.cell(row=r, column=c).value is not None 
               for c in range(1, ws.max_column + 1)):
            for c in range(1, ws.max_column + 1):
                ws.cell(row=r, column=c).border = bd

    print("테두리 적용 완료")


# 엑셀 파일 및 워크시트 생성
def create_report():
    """
    - test_report/REPORT_YYYY.MM.xlsx 파일이 없으면 생성(헤더 포함), 있으면 로드
    - 오늘 날짜 기반 시트(YY.MM.DD)가 없으면 생성 또는 기본 시트 이름 변경
    """
    # 1) 오늘 날짜 기반 파일명·시트명
    today       = datetime.now()
    folder_name = today.strftime("%Y.%m")      # ex: "2025.06"
    sheet_name  = today.strftime("%y.%m.%d")   # ex: "25.06.26"

    # 2) test_report 폴더 준비
    base_dir   = os.getcwd()
    target_dir = os.path.join(base_dir, "test_report")
    os.makedirs(target_dir, exist_ok=True)

    # 3) 파일 경로 정의
    file_name = f"REPORT_{folder_name}.xlsx"
    file_path = os.path.join(target_dir, file_name)

    # 4) 워크북 로드 or 신규 생성 플래그
    if os.path.exists(file_path):
        wb = load_workbook(file_path)
        is_new_wb = False
    else:
        wb = Workbook()
        is_new_wb = True

    # 헤더용 스타일 미리 정의
    headers = ["class_name", "content_name", "content_thumb", "capture_screen", "is_video_playing"]
    fill    = PatternFill(fill_type="solid", start_color="DDDDDD", end_color="DDDDDD")
    font    = Font(bold=True)

    # 5) 워크시트 처리
    # 5-1) 신규 워크북: 기본 시트에 이름 변경 + 헤더 추가
    if is_new_wb:        
        ws = wb.active
        ws.title = sheet_name
        ws.append(headers)
        for cell in ws[1]:
            cell.fill = fill
            cell.font = font
        print("신규 워크북 생성, 기본 시트 이름 변경:", sheet_name)
        wb.save(file_path)

    # 5-2) 기존 워크북: 시트 유무만 체크
    else:        
        if sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            print("기존 시트 로드:", sheet_name)
        else:
            ws = wb.create_sheet(title=sheet_name)
            ws.append(headers)
            for cell in ws[1]:
                cell.fill = fill
                cell.font = font
            print("신규 시트 생성:", sheet_name)

    return file_path, wb, ws