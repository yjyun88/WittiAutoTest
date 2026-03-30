# Main.py

import sys
import os
import subprocess, re
import logging
import shutil
from pathlib import Path

from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QApplication, QMessageBox

from AutoTest import AutoTest_Start
from Main_Window import Ui_MainWindow
from multiprocessing import Process, Queue, freeze_support

from request_API import (
    login_step1,
    login_step2_for_all_children,
    get_curriculum_response,
    complete_today_missions,
    class_list,
    student_list_by_class,
    authenticate_study_access,
    authenticate_study_access_detailed,
    get_study_access_auth,
    get_parent_report,
    post_attendance_curriculum,
    get_witti_school_main,
    get_aram_bookworld_subject,
    get_witti_school_ebook_main,
    get_tv_main,
    get_teacher_activity_report,
)

def get_adb_path():
    """
    Return bundled adb.exe path.
    In development mode, use ./adb/adb.exe.
    In PyInstaller onefile mode, files are unpacked under sys._MEIPASS.
    """
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.abspath(".")
    return os.path.join(base, "adb", "adb.exe")


def run_adb(args, **popen_kwargs):
    """
    Run adb command and return output.
    Uses check_output by default.
    Example: run_adb(["devices", "-l"], text=True)
    """
    adb = get_adb_path()
    return subprocess.check_output([adb] + args, **popen_kwargs)


def ensure_adb_server():
    """
    Restart bundled adb server to avoid conflicts.
    Failures are ignored to keep app flow running.
    """
    try:
        subprocess.check_output([get_adb_path(), "kill-server"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    try:
        subprocess.check_output([get_adb_path(), "start-server"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def ensure_adb_keys(app_name="AutoTest"):
    """
    1) Pin key path to %LOCALAPPDATA%\\{app_name}\\.android
    2) Copy existing user keys once if present
    3) Generate keys with bundled adb start-server if missing
    4) Always set ADB_VENDOR_KEYS to the pinned key folder
    """
    user_home = Path(os.path.expandvars(r"%USERPROFILE%"))
    user_dot_android = user_home / ".android"
    user_key = user_dot_android / "adbkey"
    user_key_pub = user_dot_android / "adbkey.pub"

    stable_root = Path(os.path.expandvars(r"%LOCALAPPDATA%")) / app_name / ".android"
    stable_root.mkdir(parents=True, exist_ok=True)
    stable_key = stable_root / "adbkey"
    stable_key_pub = stable_root / "adbkey.pub"

    if user_key.exists() and not stable_key.exists():
        try:
            shutil.copy2(user_key, stable_key)
            if user_key_pub.exists():
                shutil.copy2(user_key_pub, stable_key_pub)
        except Exception:
            pass

    os.environ["ADB_VENDOR_KEYS"] = str(stable_root)

    if not stable_key.exists():
        adb = get_adb_path()
        try:
            subprocess.run([adb, "start-server"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


ensure_adb_keys(app_name="AutoTest")


def worker_main(
    log_queue,
    btn_name,
    device_name,
    device_label,
    inputId,
    inputPwd,
    subjCd,
    itemCd,
    curtnSeq,
    title_name,
    server,
    study_access_mem_nm,
    study_access_mem_id,
    study_access_auth_token,
):
    import builtins, traceback
    def _print_via_queue(*args, sep=" ", end="\n", **kwargs):
        msg = sep.join(str(a) for a in args) + end
        log_queue.put(msg.rstrip("\n"))
    builtins.print = _print_via_queue

    try:
        print("워커 프로세스 시작")
        AutoTest_Start(
            btn_name,
            device_name,
            device_label,
            inputId,
            inputPwd,
            subjCd,
            itemCd,
            curtnSeq,
            title_name,
            server,
            study_access_mem_nm,
            study_access_mem_id,
            study_access_auth_token,
        )
    except Exception as e:
        print(f"[ERROR] AutoTest_Start 중 예외: {e!r}")
        print(traceback.format_exc())

# def worker_complete_missions(log_queue, user_id, user_pwd, server):
#     match server:
#         case "Prod":
#             server = "api"
#         case "QA":
#             server = "qa-api"
#         case "Dev":
#             server = "dev-api"
#         case _:
#             server = "api"
# 
#     import builtins, traceback
#     def _print_via_queue(*args, sep=" ", end="\n", **kwargs):
#         msg = sep.join(str(a) for a in args) + end
#         log_queue.put(msg.rstrip("\n"))
#     builtins.print = _print_via_queue
# 
#     try:
#         print("오늘의 미션 완료 처리를 시작합니다...")
# 
#         authToken = login_step1(user_id, user_pwd, server)
#         if not authToken:
#             print("[ERROR] 1차 로그인 실패. ID/PW나 서버 설정을 확인하세요.")
#             return
#         print("[INFO] login_step1 ??? childList? ?? ??? ?? ??? ??? ? ????.")
#         return
# 
#         auth_tokens_by_child = login_step2_for_all_children(authToken, childIds, server)
#         if not auth_tokens_by_child:
#             print("[ERROR] 2차 로그인 실패: 모든 자녀의 토큰을 발급받지 못했습니다.")
#             return
# 
#         all_child_missions = []
# 
#         for child_id, child_name in zip(childIds, childNms):
#             child_specific_auth_token = auth_tokens_by_child.get(child_id)
#             if not child_specific_auth_token:
#                 print(f"[WARN] '{child_name}'({child_id})의 2차 로그인 토큰을 찾을 수 없습니다. 이 자녀의 미션을 건너뜁니다.")
#                 continue
#             
#             response = get_curriculum_response(child_specific_auth_token, child_id, server)
# 
#             if response is None:
#                 print(f"[WARN] '{child_name}'의 커리큘럼 조회 실패. 다음 자녀로 넘어갑니다.")
#                 continue
# 
#             try:
#                 data = response.json()
#                 mission_list = data.get("result", {}).get("missionList", [])
# 
#                 if not mission_list:
#                     print(f"[INFO] '{child_name}'에게 할당된 오늘의 미션이 없습니다.")
#                     continue
# 
#                 for mission in mission_list:
#                     mission['childNm'] = child_name
#                     mission['childId'] = child_id
#                     all_child_missions.append(mission)
# 
#             except Exception as e:
#                 print(f"[ERROR] '{child_name}'의 커리큘럼 응답 파싱 중 오류 발생: {e}")
#                 continue
# 
#         complete_today_missions(auth_tokens_by_child, all_child_missions, server)
# 
#         print("\n오늘의 미션 완료 처리가 성공적으로 종료되었습니다.")
# 
#     except Exception as e:
#         print(f"[ERROR] 미션 완료 처리 중 예외 발생: {e!r}")
#         print(traceback.format_exc())
# 
# 

# ── API 리포트 공통 유틸 ──────────────────────────────────────────
_API_REPORT_HEADERS = [
    "tested_at", "server_api", "classId", "classNm", "targetAge",
    "studentId", "studentNm", "loginIdUsed", "httpStatus", "status",
    "memNm", "memId", "error",
]


def init_api_report(report_name, user_id):
    """API 테스트 리포트 워크북을 생성/로드한다. {report_name}_{YYMMDD}.xlsx"""
    from datetime import datetime
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font, Alignment

    report_dir = os.path.join(os.getcwd(), "test_report", "api_test")
    os.makedirs(report_dir, exist_ok=True)
    date_suffix = datetime.now().strftime("%y%m%d")
    report_path = os.path.join(report_dir, f"{report_name}_{date_suffix}.xlsx")

    if os.path.exists(report_path):
        try:
            wb = load_workbook(report_path)
        except Exception:
            wb = Workbook()
    else:
        wb = Workbook()

    safe_user_id = re.sub(r'[\\/:*?"<>|]', "_", str(user_id))
    sheet_name = safe_user_id[:31]

    if sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
    else:
        ws = wb.create_sheet(title=sheet_name)
        ws.append(_API_REPORT_HEADERS)
        for c in ws[1]:
            c.font = Font(bold=True)
            c.alignment = Alignment(horizontal="center", vertical="center")

    if "Sheet" in wb.sheetnames:
        default_ws = wb["Sheet"]
        if default_ws.max_row <= 1 and default_ws.cell(1, 1).value is None:
            wb.remove(default_ws)

    return report_path, wb, ws


def style_api_row(ws, row, headers, ok, student_nm, mem_nm):
    """API 리포트 행에 상태 스타일을 적용한다."""
    from openpyxl.styles import Font, PatternFill, Alignment

    status_col_idx = headers.index("status") + 1
    student_nm_col_idx = headers.index("studentNm") + 1
    mem_nm_col_idx = headers.index("memNm") + 1

    for col_idx in range(1, len(headers) + 1):
        ws.cell(row=row, column=col_idx).alignment = Alignment(horizontal="center", vertical="center")

    status_cell = ws.cell(row=row, column=status_col_idx)
    if ok:
        status_cell.font = Font(color="008000", bold=True)
        status_cell.fill = PatternFill(fill_type="solid", start_color="CCFFCC", end_color="CCFFCC")
    else:
        status_cell.font = Font(color="FF0000", bold=True)
        status_cell.fill = PatternFill(fill_type="solid", start_color="FFCCCC", end_color="FFCCCC")

    if student_nm != mem_nm:
        mismatch_fill = PatternFill(fill_type="solid", start_color="FFCCCC", end_color="FFCCCC")
        mismatch_font = Font(color="FF0000", bold=True)
        ws.cell(row=row, column=student_nm_col_idx).font = mismatch_font
        ws.cell(row=row, column=student_nm_col_idx).fill = mismatch_fill
        ws.cell(row=row, column=mem_nm_col_idx).font = mismatch_font
        ws.cell(row=row, column=mem_nm_col_idx).fill = mismatch_fill


def save_api_report(wb, ws, report_path):
    """컬럼 너비 자동 조절 후 저장한다."""
    for col in ws.columns:
        col_letter = col[0].column_letter
        max_len = 0
        for cell in col:
            if cell.value is None:
                continue
            max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(60, max(12, max_len + 2))
    wb.save(report_path)
    print(f"[INFO] report saved: {report_path}")

# ── API 리포트 공통 유틸 끝 ───────────────────────────────────────


def worker_study_access_bulk(log_queue, user_id, user_pwd, server, device_label):
    env_code = {
        "Prod": "PRD",
        "QA": "QA",
        "Dev": "DEV",
    }.get(server, str(server).upper())

    match server:
        case "Prod":
            server = "api"
        case "QA":
            server = "qa-api"
        case "Dev":
            server = "dev-api"
        case _:
            server = "api"

    import builtins
    import traceback
    from datetime import datetime

    def _print_via_queue(*args, sep=" ", end="\n", **kwargs):
        msg = sep.join(str(a) for a in args) + end
        log_queue.put(msg.rstrip("\n"))

    builtins.print = _print_via_queue

    try:
        print("[INFO] study/access bulk test started")
        token = login_step1(user_id, user_pwd, server)
        if not token:
            print("[ERROR] login failed. cannot load classes.")
            return

        class_resp = class_list(token, user_id, server)
        if class_resp is None:
            print("[ERROR] class list request failed.")
            return

        class_data = class_resp.json()
        classes = class_data.get("result", {}).get("classList", [])
        print(f"[INFO] classes loaded: {len(classes)}")

        report_path, wb, ws = init_api_report("study_access_result", user_id)

        total_students = 0
        success_count = 0
        fail_count = 0

        for cls in classes:
            class_id = str(cls.get("classId", "")).strip()
            class_nm = str(cls.get("classNm", "")).strip()
            target_age = str(cls.get("targetAge", "")).strip()
            if not class_id:
                continue

            student_resp = student_list_by_class(token, class_id, server)
            if student_resp is None:
                print(f"[WARN] student list failed for classId={class_id}")
                continue

            students = student_resp.json().get("result", {}).get("studentList", [])
            print(f"[INFO] class={class_nm} ({class_id}), students={len(students)}")

            for student in students:
                total_students += 1
                tested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                student_id = str(student.get("studentId", "")).strip()
                student_nm = str(student.get("studentNm", "")).strip()
                login_id_used = str(
                    student.get("loginId")
                    or student.get("studentLoginId")
                    or user_id
                ).strip()

                result = authenticate_study_access_detailed(student_id, login_id_used, server)
                data = result.get("data") if isinstance(result, dict) else None
                if not isinstance(data, dict):
                    data = {}
                api_result = data.get("result", {}) if isinstance(data.get("result", {}), dict) else {}

                ok = bool(result.get("ok"))
                if ok:
                    success_count += 1
                else:
                    fail_count += 1

                mem_nm = str(api_result.get("memNm", "")).strip()

                ws.append([
                    tested_at,
                    env_code,
                    class_id,
                    class_nm,
                    target_age,
                    student_id,
                    student_nm,
                    login_id_used,
                    result.get("status_code"),
                    "PASS" if ok else "FAIL",
                    mem_nm,
                    api_result.get("memId", ""),
                    result.get("error", ""),
                ])
                style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, ok, student_nm, mem_nm)

        save_api_report(wb, ws, report_path)
        print(
            f"[INFO] study/access bulk completed. total={total_students}, "
            f"success={success_count}, fail={fail_count}"
        )

    except Exception as e:
        print(f"[ERROR] study/access bulk exception: {e!r}")
        print(traceback.format_exc())


def worker_curriculum_bulk(log_queue, user_id, user_pwd, server, device_label):
    env_code = {
        "Prod": "PRD",
        "QA": "QA",
        "Dev": "DEV",
    }.get(server, str(server).upper())

    match server:
        case "Prod":
            server = "api"
        case "QA":
            server = "qa-api"
        case "Dev":
            server = "dev-api"
        case _:
            server = "api"

    import builtins
    import traceback
    from datetime import datetime

    def _print_via_queue(*args, sep=" ", end="\n", **kwargs):
        msg = sep.join(str(a) for a in args) + end
        log_queue.put(msg.rstrip("\n"))

    builtins.print = _print_via_queue

    try:
        print("[INFO] curriculum bulk test started")
        token = login_step1(user_id, user_pwd, server)
        if not token:
            print("[ERROR] login failed. cannot load classes.")
            return

        class_resp = class_list(token, user_id, server)
        if class_resp is None:
            print("[ERROR] class list request failed.")
            return

        class_data = class_resp.json()
        classes = class_data.get("result", {}).get("classList", [])
        print(f"[INFO] classes loaded: {len(classes)}")

        report_path, wb, ws = init_api_report("curriculum_result", user_id)

        total_students = 0
        success_count = 0
        fail_count = 0

        for cls in classes:
            class_id = str(cls.get("classId", "")).strip()
            class_nm = str(cls.get("classNm", "")).strip()
            target_age = str(cls.get("targetAge", "")).strip()
            if not class_id:
                continue

            student_resp = student_list_by_class(token, class_id, server)
            if student_resp is None:
                print(f"[WARN] student list failed for classId={class_id}")
                continue

            students = student_resp.json().get("result", {}).get("studentList", [])
            print(f"[INFO] class={class_nm} ({class_id}), students={len(students)}")

            for student in students:
                total_students += 1
                tested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                student_id = str(student.get("studentId", "")).strip()
                student_nm = str(student.get("studentNm", "")).strip()
                login_id_used = str(
                    student.get("loginId")
                    or student.get("studentLoginId")
                    or user_id
                ).strip()

                # Step 1: study/access to get child authToken and memId (childId)
                access_result = authenticate_study_access_detailed(student_id, login_id_used, server)
                access_data = access_result.get("data") if isinstance(access_result, dict) else None
                if not isinstance(access_data, dict):
                    access_data = {}
                access_api_result = access_data.get("result", {}) if isinstance(access_data.get("result", {}), dict) else {}

                child_auth_token = str(access_api_result.get("authToken", "")).strip()
                child_id = str(access_api_result.get("memId", "")).strip()
                mem_nm = str(access_api_result.get("memNm", "")).strip()

                if not access_result.get("ok") or not child_auth_token or not child_id:
                    fail_count += 1
                    ws.append([
                        tested_at,
                        env_code,
                        class_id,
                        class_nm,
                        target_age,
                        student_id,
                        student_nm,
                        login_id_used,
                        access_result.get("status_code"),
                        "FAIL",
                        mem_nm,
                        child_id,
                        access_result.get("error", "") or "study/access failed",
                    ])
                    style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, False, student_nm, mem_nm)
                    continue

                # Step 2: call curriculum API with child's authToken and memId as childId
                try:
                    curriculum_resp = get_curriculum_response(child_auth_token, child_id, server)
                    if curriculum_resp is not None:
                        http_status = curriculum_resp.status_code
                        ok = curriculum_resp.ok
                        error_msg = "" if ok else curriculum_resp.text
                    else:
                        http_status = None
                        ok = False
                        error_msg = "curriculum response is None"
                except Exception as e:
                    http_status = None
                    ok = False
                    error_msg = str(e)

                if ok:
                    success_count += 1
                else:
                    fail_count += 1

                ws.append([
                    tested_at,
                    env_code,
                    class_id,
                    class_nm,
                    target_age,
                    student_id,
                    student_nm,
                    login_id_used,
                    http_status,
                    "PASS" if ok else "FAIL",
                    mem_nm,
                    child_id,
                    error_msg,
                ])
                style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, ok, student_nm, mem_nm)

        save_api_report(wb, ws, report_path)
        print(
            f"[INFO] curriculum bulk completed. total={total_students}, "
            f"success={success_count}, fail={fail_count}"
        )

    except Exception as e:
        print(f"[ERROR] curriculum bulk exception: {e!r}")
        print(traceback.format_exc())


def worker_attendance_curriculum_bulk(log_queue, user_id, user_pwd, server, device_label):
    env_code = {
        "Prod": "PRD",
        "QA": "QA",
        "Dev": "DEV",
    }.get(server, str(server).upper())

    match server:
        case "Prod":
            server = "api"
        case "QA":
            server = "qa-api"
        case "Dev":
            server = "dev-api"
        case _:
            server = "api"

    import builtins
    import traceback
    from datetime import datetime

    def _print_via_queue(*args, sep=" ", end="\n", **kwargs):
        msg = sep.join(str(a) for a in args) + end
        log_queue.put(msg.rstrip("\n"))

    builtins.print = _print_via_queue

    try:
        print("[INFO] attendance/curriculum bulk test started")
        token = login_step1(user_id, user_pwd, server)
        if not token:
            print("[ERROR] login failed. cannot load classes.")
            return

        class_resp = class_list(token, user_id, server)
        if class_resp is None:
            print("[ERROR] class list request failed.")
            return

        class_data = class_resp.json()
        classes = class_data.get("result", {}).get("classList", [])
        print(f"[INFO] classes loaded: {len(classes)}")

        report_path, wb, ws = init_api_report("attendance_curriculum_result", user_id)

        total_students = 0
        success_count = 0
        fail_count = 0

        for cls in classes:
            class_id = str(cls.get("classId", "")).strip()
            class_nm = str(cls.get("classNm", "")).strip()
            target_age = str(cls.get("targetAge", "")).strip()
            if not class_id:
                continue

            student_resp = student_list_by_class(token, class_id, server)
            if student_resp is None:
                print(f"[WARN] student list failed for classId={class_id}")
                continue

            students = student_resp.json().get("result", {}).get("studentList", [])
            print(f"[INFO] class={class_nm} ({class_id}), students={len(students)}")

            for student in students:
                total_students += 1
                tested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                student_id = str(student.get("studentId", "")).strip()
                student_nm = str(student.get("studentNm", "")).strip()
                login_id_used = str(
                    student.get("loginId")
                    or student.get("studentLoginId")
                    or user_id
                ).strip()

                # Step 1: study/access to get child authToken
                access_result = authenticate_study_access_detailed(student_id, login_id_used, server)
                access_data = access_result.get("data") if isinstance(access_result, dict) else None
                if not isinstance(access_data, dict):
                    access_data = {}
                access_api_result = access_data.get("result", {}) if isinstance(access_data.get("result", {}), dict) else {}

                child_auth_token = str(access_api_result.get("authToken", "")).strip()
                child_id = str(access_api_result.get("memId", "")).strip()
                mem_nm = str(access_api_result.get("memNm", "")).strip()

                if not access_result.get("ok") or not child_auth_token:
                    fail_count += 1
                    ws.append([
                        tested_at, env_code, class_id, class_nm, target_age,
                        student_id, student_nm, login_id_used,
                        access_result.get("status_code"),
                        "FAIL", mem_nm, child_id,
                        access_result.get("error", "") or "study/access failed",
                    ])
                    style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, False, student_nm, mem_nm)
                    continue

                # Step 2: call attendance/curriculum API
                try:
                    att_resp = post_attendance_curriculum(child_auth_token, server)
                    if att_resp is not None:
                        http_status = att_resp.status_code
                        ok = att_resp.ok
                        error_msg = "" if ok else att_resp.text
                    else:
                        http_status = None
                        ok = False
                        error_msg = "attendance/curriculum response is None"
                except Exception as e:
                    http_status = None
                    ok = False
                    error_msg = str(e)

                if ok:
                    success_count += 1
                else:
                    fail_count += 1

                ws.append([
                    tested_at, env_code, class_id, class_nm, target_age,
                    student_id, student_nm, login_id_used,
                    http_status,
                    "PASS" if ok else "FAIL",
                    mem_nm, child_id, error_msg,
                ])
                style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, ok, student_nm, mem_nm)

        save_api_report(wb, ws, report_path)
        print(
            f"[INFO] attendance/curriculum bulk completed. total={total_students}, "
            f"success={success_count}, fail={fail_count}"
        )

    except Exception as e:
        print(f"[ERROR] attendance/curriculum bulk exception: {e!r}")
        print(traceback.format_exc())


def worker_witti_school_main_bulk(log_queue, user_id, user_pwd, server, device_label):
    env_code = {
        "Prod": "PRD",
        "QA": "QA",
        "Dev": "DEV",
    }.get(server, str(server).upper())

    match server:
        case "Prod":
            server = "api"
        case "QA":
            server = "qa-api"
        case "Dev":
            server = "dev-api"
        case _:
            server = "api"

    import builtins
    import traceback
    from datetime import datetime

    def _print_via_queue(*args, sep=" ", end="\n", **kwargs):
        msg = sep.join(str(a) for a in args) + end
        log_queue.put(msg.rstrip("\n"))

    builtins.print = _print_via_queue

    try:
        print("[INFO] witti-school/main bulk test started")
        token = login_step1(user_id, user_pwd, server)
        if not token:
            print("[ERROR] login failed. cannot load classes.")
            return

        class_resp = class_list(token, user_id, server)
        if class_resp is None:
            print("[ERROR] class list request failed.")
            return

        class_data = class_resp.json()
        classes = class_data.get("result", {}).get("classList", [])
        print(f"[INFO] classes loaded: {len(classes)}")

        report_path, wb, ws = init_api_report("witti_school_main_result", user_id)

        total_students = 0
        success_count = 0
        fail_count = 0

        for cls in classes:
            class_id = str(cls.get("classId", "")).strip()
            class_nm = str(cls.get("classNm", "")).strip()
            target_age = str(cls.get("targetAge", "")).strip()
            if not class_id:
                continue

            student_resp = student_list_by_class(token, class_id, server)
            if student_resp is None:
                print(f"[WARN] student list failed for classId={class_id}")
                continue

            students = student_resp.json().get("result", {}).get("studentList", [])
            print(f"[INFO] class={class_nm} ({class_id}), students={len(students)}")

            for student in students:
                total_students += 1
                tested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                student_id = str(student.get("studentId", "")).strip()
                student_nm = str(student.get("studentNm", "")).strip()
                login_id_used = str(
                    student.get("loginId")
                    or student.get("studentLoginId")
                    or user_id
                ).strip()

                # Step 1: study/access to get child authToken
                access_result = authenticate_study_access_detailed(student_id, login_id_used, server)
                access_data = access_result.get("data") if isinstance(access_result, dict) else None
                if not isinstance(access_data, dict):
                    access_data = {}
                access_api_result = access_data.get("result", {}) if isinstance(access_data.get("result", {}), dict) else {}

                child_auth_token = str(access_api_result.get("authToken", "")).strip()
                child_id = str(access_api_result.get("memId", "")).strip()
                mem_nm = str(access_api_result.get("memNm", "")).strip()

                if not access_result.get("ok") or not child_auth_token:
                    fail_count += 1
                    ws.append([
                        tested_at, env_code, class_id, class_nm, target_age,
                        student_id, student_nm, login_id_used,
                        access_result.get("status_code"),
                        "FAIL", mem_nm, child_id,
                        access_result.get("error", "") or "study/access failed",
                    ])
                    style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, False, student_nm, mem_nm)
                    continue

                # Step 2: call witti-school/main API
                try:
                    resp = get_witti_school_main(child_auth_token, server)
                    if resp is not None:
                        http_status = resp.status_code
                        ok = resp.ok
                        error_msg = "" if ok else resp.text
                    else:
                        http_status = None
                        ok = False
                        error_msg = "witti-school/main response is None"
                except Exception as e:
                    http_status = None
                    ok = False
                    error_msg = str(e)

                if ok:
                    success_count += 1
                else:
                    fail_count += 1

                ws.append([
                    tested_at, env_code, class_id, class_nm, target_age,
                    student_id, student_nm, login_id_used,
                    http_status,
                    "PASS" if ok else "FAIL",
                    mem_nm, child_id, error_msg,
                ])
                style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, ok, student_nm, mem_nm)

        save_api_report(wb, ws, report_path)
        print(
            f"[INFO] witti-school/main bulk completed. total={total_students}, "
            f"success={success_count}, fail={fail_count}"
        )

    except Exception as e:
        print(f"[ERROR] witti-school/main bulk exception: {e!r}")
        print(traceback.format_exc())


def worker_aram_bookworld_subject_bulk(log_queue, user_id, user_pwd, server, device_label):
    env_code = {
        "Prod": "PRD",
        "QA": "QA",
        "Dev": "DEV",
    }.get(server, str(server).upper())

    match server:
        case "Prod":
            server = "api"
        case "QA":
            server = "qa-api"
        case "Dev":
            server = "dev-api"
        case _:
            server = "api"

    import builtins
    import traceback
    from datetime import datetime

    def _print_via_queue(*args, sep=" ", end="\n", **kwargs):
        msg = sep.join(str(a) for a in args) + end
        log_queue.put(msg.rstrip("\n"))

    builtins.print = _print_via_queue

    try:
        print("[INFO] aram-bookworld/subject bulk test started")
        token = login_step1(user_id, user_pwd, server)
        if not token:
            print("[ERROR] login failed. cannot load classes.")
            return

        class_resp = class_list(token, user_id, server)
        if class_resp is None:
            print("[ERROR] class list request failed.")
            return

        class_data = class_resp.json()
        classes = class_data.get("result", {}).get("classList", [])
        print(f"[INFO] classes loaded: {len(classes)}")

        report_path, wb, ws = init_api_report("aram_bookworld_subject_result", user_id)

        total_students = 0
        success_count = 0
        fail_count = 0

        for cls in classes:
            class_id = str(cls.get("classId", "")).strip()
            class_nm = str(cls.get("classNm", "")).strip()
            target_age = str(cls.get("targetAge", "")).strip()
            if not class_id:
                continue

            student_resp = student_list_by_class(token, class_id, server)
            if student_resp is None:
                print(f"[WARN] student list failed for classId={class_id}")
                continue

            students = student_resp.json().get("result", {}).get("studentList", [])
            print(f"[INFO] class={class_nm} ({class_id}), students={len(students)}")

            for student in students:
                total_students += 1
                tested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                student_id = str(student.get("studentId", "")).strip()
                student_nm = str(student.get("studentNm", "")).strip()
                login_id_used = str(
                    student.get("loginId")
                    or student.get("studentLoginId")
                    or user_id
                ).strip()

                # Step 1: study/access
                access_result = authenticate_study_access_detailed(student_id, login_id_used, server)
                access_data = access_result.get("data") if isinstance(access_result, dict) else None
                if not isinstance(access_data, dict):
                    access_data = {}
                access_api_result = access_data.get("result", {}) if isinstance(access_data.get("result", {}), dict) else {}

                child_auth_token = str(access_api_result.get("authToken", "")).strip()
                child_id = str(access_api_result.get("memId", "")).strip()
                mem_nm = str(access_api_result.get("memNm", "")).strip()

                if not access_result.get("ok") or not child_auth_token:
                    fail_count += 1
                    ws.append([
                        tested_at, env_code, class_id, class_nm, target_age,
                        student_id, student_nm, login_id_used,
                        access_result.get("status_code"),
                        "FAIL", mem_nm, child_id,
                        access_result.get("error", "") or "study/access failed",
                    ])
                    style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, False, student_nm, mem_nm)
                    continue

                # Step 2: witti-school/main으로 prodId, ptnrId 추출
                ptnr_id = "1102"
                prod_id = "P0001"
                try:
                    main_resp = get_witti_school_main(child_auth_token, server)
                    if main_resp and main_resp.ok:
                        main_data = main_resp.json().get("result", {})
                        prod_list = main_data.get("prodList") or main_data.get("productList") or []
                        if prod_list:
                            prod_id = prod_list[0].get("prodId", prod_id)
                            ptnr_id = str(prod_list[0].get("ptnrId", ptnr_id))
                except Exception:
                    pass

                # Step 3: aram-bookworld/subject 호출
                try:
                    resp = get_aram_bookworld_subject(child_auth_token, ptnr_id, prod_id, server)
                    if resp is not None:
                        http_status = resp.status_code
                        ok = resp.ok
                        error_msg = "" if ok else resp.text
                    else:
                        http_status = None
                        ok = False
                        error_msg = "aram-bookworld/subject response is None"
                except Exception as e:
                    http_status = None
                    ok = False
                    error_msg = str(e)

                if ok:
                    success_count += 1
                else:
                    fail_count += 1

                ws.append([
                    tested_at, env_code, class_id, class_nm, target_age,
                    student_id, student_nm, login_id_used,
                    http_status,
                    "PASS" if ok else "FAIL",
                    mem_nm, child_id, error_msg,
                ])
                style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, ok, student_nm, mem_nm)

        save_api_report(wb, ws, report_path)
        print(
            f"[INFO] aram-bookworld/subject bulk completed. total={total_students}, "
            f"success={success_count}, fail={fail_count}"
        )

    except Exception as e:
        print(f"[ERROR] aram-bookworld/subject bulk exception: {e!r}")
        print(traceback.format_exc())


def _make_simple_get_worker(api_name, report_file_name, api_call_fn):
    """GET API (파라미터 없이 자녀 토큰만 필요)용 bulk worker를 생성하는 팩토리."""

    def worker(log_queue, user_id, user_pwd, server, device_label):
        env_code = {
            "Prod": "PRD", "QA": "QA", "Dev": "DEV",
        }.get(server, str(server).upper())

        match server:
            case "Prod":
                server = "api"
            case "QA":
                server = "qa-api"
            case "Dev":
                server = "dev-api"
            case _:
                server = "api"

        import builtins, traceback
        from datetime import datetime

        def _print_via_queue(*args, sep=" ", end="\n", **kwargs):
            msg = sep.join(str(a) for a in args) + end
            log_queue.put(msg.rstrip("\n"))

        builtins.print = _print_via_queue

        try:
            print(f"[INFO] {api_name} bulk test started")
            token = login_step1(user_id, user_pwd, server)
            if not token:
                print("[ERROR] login failed.")
                return

            class_resp = class_list(token, user_id, server)
            if class_resp is None:
                print("[ERROR] class list request failed.")
                return

            classes = class_resp.json().get("result", {}).get("classList", [])
            print(f"[INFO] classes loaded: {len(classes)}")

            report_path, wb, ws = init_api_report(report_file_name, user_id)
            total, success, fail = 0, 0, 0

            for cls in classes:
                class_id = str(cls.get("classId", "")).strip()
                class_nm = str(cls.get("classNm", "")).strip()
                target_age = str(cls.get("targetAge", "")).strip()
                if not class_id:
                    continue

                stu_resp = student_list_by_class(token, class_id, server)
                if stu_resp is None:
                    print(f"[WARN] student list failed for classId={class_id}")
                    continue

                students = stu_resp.json().get("result", {}).get("studentList", [])
                print(f"[INFO] class={class_nm} ({class_id}), students={len(students)}")

                for student in students:
                    total += 1
                    tested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    student_id = str(student.get("studentId", "")).strip()
                    student_nm = str(student.get("studentNm", "")).strip()
                    login_id_used = str(
                        student.get("loginId") or student.get("studentLoginId") or user_id
                    ).strip()

                    access_result = authenticate_study_access_detailed(student_id, login_id_used, server)
                    access_data = access_result.get("data") if isinstance(access_result, dict) else None
                    if not isinstance(access_data, dict):
                        access_data = {}
                    api_res = access_data.get("result", {}) if isinstance(access_data.get("result", {}), dict) else {}

                    child_auth = str(api_res.get("authToken", "")).strip()
                    child_id = str(api_res.get("memId", "")).strip()
                    mem_nm = str(api_res.get("memNm", "")).strip()

                    if not access_result.get("ok") or not child_auth:
                        fail += 1
                        ws.append([
                            tested_at, env_code, class_id, class_nm, target_age,
                            student_id, student_nm, login_id_used,
                            access_result.get("status_code"),
                            "FAIL", mem_nm, child_id,
                            access_result.get("error", "") or "study/access failed",
                        ])
                        style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, False, student_nm, mem_nm)
                        continue

                    try:
                        resp = api_call_fn(child_auth, server)
                        if resp is not None:
                            http_status = resp.status_code
                            ok = resp.ok
                            error_msg = "" if ok else resp.text
                        else:
                            http_status = None
                            ok = False
                            error_msg = f"{api_name} response is None"
                    except Exception as e:
                        http_status = None
                        ok = False
                        error_msg = str(e)

                    if ok:
                        success += 1
                    else:
                        fail += 1

                    ws.append([
                        tested_at, env_code, class_id, class_nm, target_age,
                        student_id, student_nm, login_id_used,
                        http_status, "PASS" if ok else "FAIL",
                        mem_nm, child_id, error_msg,
                    ])
                    style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, ok, student_nm, mem_nm)

            save_api_report(wb, ws, report_path)
            print(f"[INFO] {api_name} bulk completed. total={total}, success={success}, fail={fail}")

        except Exception as e:
            print(f"[ERROR] {api_name} bulk exception: {e!r}")
            print(traceback.format_exc())

    return worker


worker_ebook_main_bulk = _make_simple_get_worker(
    "e-book/main", "ebook_main_result", get_witti_school_ebook_main)

worker_tv_main_bulk = _make_simple_get_worker(
    "tv/main", "tv_main_result", get_tv_main)


def worker_parent_report_bulk(log_queue, user_id, user_pwd, server, device_label):
    env_code = {
        "Prod": "PRD",
        "QA": "QA",
        "Dev": "DEV",
    }.get(server, str(server).upper())

    match server:
        case "Prod":
            server = "api"
        case "QA":
            server = "qa-api"
        case "Dev":
            server = "dev-api"
        case _:
            server = "api"

    import builtins
    import traceback
    from datetime import datetime

    def _print_via_queue(*args, sep=" ", end="\n", **kwargs):
        msg = sep.join(str(a) for a in args) + end
        log_queue.put(msg.rstrip("\n"))

    builtins.print = _print_via_queue

    try:
        print("[INFO] parent report bulk test started")
        token = login_step1(user_id, user_pwd, server)
        if not token:
            print("[ERROR] login failed. cannot load classes.")
            return

        class_resp = class_list(token, user_id, server)
        if class_resp is None:
            print("[ERROR] class list request failed.")
            return

        class_data = class_resp.json()
        classes = class_data.get("result", {}).get("classList", [])
        print(f"[INFO] classes loaded: {len(classes)}")

        report_path, wb, ws = init_api_report("parent_report_result", user_id)

        total_students = 0
        success_count = 0
        fail_count = 0

        for cls in classes:
            class_id = str(cls.get("classId", "")).strip()
            class_nm = str(cls.get("classNm", "")).strip()
            target_age = str(cls.get("targetAge", "")).strip()
            if not class_id:
                continue

            student_resp = student_list_by_class(token, class_id, server)
            if student_resp is None:
                print(f"[WARN] student list failed for classId={class_id}")
                continue

            students = student_resp.json().get("result", {}).get("studentList", [])
            print(f"[INFO] class={class_nm} ({class_id}), students={len(students)}")

            for student in students:
                total_students += 1
                tested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                student_id = str(student.get("studentId", "")).strip()
                student_nm = str(student.get("studentNm", "")).strip()
                login_id_used = str(
                    student.get("loginId")
                    or student.get("studentLoginId")
                    or user_id
                ).strip()

                # Step 1: study/access to get child authToken, memId
                access_result = authenticate_study_access_detailed(student_id, login_id_used, server)
                access_data = access_result.get("data") if isinstance(access_result, dict) else None
                if not isinstance(access_data, dict):
                    access_data = {}
                access_api_result = access_data.get("result", {}) if isinstance(access_data.get("result", {}), dict) else {}

                child_auth_token = str(access_api_result.get("authToken", "")).strip()
                child_id = str(access_api_result.get("memId", "")).strip()
                mem_nm = str(access_api_result.get("memNm", "")).strip()

                if not access_result.get("ok") or not child_auth_token or not child_id:
                    fail_count += 1
                    ws.append([
                        tested_at,
                        env_code,
                        class_id,
                        class_nm,
                        target_age,
                        student_id,
                        student_nm,
                        login_id_used,
                        access_result.get("status_code"),
                        "FAIL",
                        mem_nm,
                        child_id,
                        access_result.get("error", "") or "study/access failed",
                    ])
                    style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, False, student_nm, mem_nm)
                    continue

                # Step 2: 커리큘럼 API에서 year, month, week 조회
                cur_resp = get_curriculum_response(child_auth_token, child_id, server)
                if cur_resp is not None and cur_resp.ok:
                    cur_result = cur_resp.json().get("result", {})
                    year = datetime.now().year
                    month = cur_result.get("month")
                    week = cur_result.get("week")
                    curriculum_tp = int(cur_result.get("curriculumTp", 0))
                    child_age_from_class = cur_result.get("childAge", 0)
                else:
                    fail_count += 1
                    cur_status = cur_resp.status_code if cur_resp else None
                    cur_error = cur_resp.text if cur_resp else "curriculum response is None"
                    ws.append([
                        tested_at, env_code, class_id, class_nm, target_age,
                        student_id, student_nm, login_id_used,
                        cur_status, "FAIL", mem_nm, child_id,
                        f"curriculum failed: {cur_error}",
                    ])
                    style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, False, student_nm, mem_nm)
                    continue

                # Step 3: call parentReport API
                try:
                    report_resp = get_parent_report(
                        child_auth_token, child_id, child_age_from_class,
                        curriculum_tp, year, month, week, server,
                    )
                    if report_resp is not None:
                        http_status = report_resp.status_code
                        ok = report_resp.ok
                        error_msg = "" if ok else report_resp.text
                    else:
                        http_status = None
                        ok = False
                        error_msg = "parentReport response is None"
                except Exception as e:
                    http_status = None
                    ok = False
                    error_msg = str(e)

                if ok:
                    success_count += 1
                else:
                    fail_count += 1

                ws.append([
                    tested_at,
                    env_code,
                    class_id,
                    class_nm,
                    target_age,
                    student_id,
                    student_nm,
                    login_id_used,
                    http_status,
                    "PASS" if ok else "FAIL",
                    mem_nm,
                    child_id,
                    error_msg,
                ])
                style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, ok, student_nm, mem_nm)

        save_api_report(wb, ws, report_path)
        print(
            f"[INFO] parent report bulk completed. total={total_students}, "
            f"success={success_count}, fail={fail_count}"
        )

    except Exception as e:
        print(f"[ERROR] parent report bulk exception: {e!r}")
        print(traceback.format_exc())


def worker_teacher_activity_report_bulk(log_queue, user_id, user_pwd, server, device_label):
    env_code = {
        "Prod": "PRD", "QA": "QA", "Dev": "DEV",
    }.get(server, str(server).upper())

    match server:
        case "Prod":
            server = "api"
        case "QA":
            server = "qa-api"
        case "Dev":
            server = "dev-api"
        case _:
            server = "api"

    import builtins
    import traceback
    from datetime import datetime

    def _print_via_queue(*args, sep=" ", end="\n", **kwargs):
        msg = sep.join(str(a) for a in args) + end
        log_queue.put(msg.rstrip("\n"))

    builtins.print = _print_via_queue

    try:
        print("[INFO] teacherActivityReport bulk test started")
        token = login_step1(user_id, user_pwd, server)
        if not token:
            print("[ERROR] login failed.")
            return

        class_resp = class_list(token, user_id, server)
        if class_resp is None:
            print("[ERROR] class list request failed.")
            return

        classes = class_resp.json().get("result", {}).get("classList", [])
        print(f"[INFO] classes loaded: {len(classes)}")

        report_path, wb, ws = init_api_report("teacher_activity_report_result", user_id)

        total_students = 0
        success_count = 0
        fail_count = 0

        for cls in classes:
            class_id = str(cls.get("classId", "")).strip()
            class_nm = str(cls.get("classNm", "")).strip()
            target_age = str(cls.get("targetAge", "")).strip()
            if not class_id:
                continue

            student_resp = student_list_by_class(token, class_id, server)
            if student_resp is None:
                print(f"[WARN] student list failed for classId={class_id}")
                continue

            students = student_resp.json().get("result", {}).get("studentList", [])
            print(f"[INFO] class={class_nm} ({class_id}), students={len(students)}")

            for student in students:
                total_students += 1
                tested_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                student_id = str(student.get("studentId", "")).strip()
                student_nm = str(student.get("studentNm", "")).strip()
                login_id_used = str(
                    student.get("loginId")
                    or student.get("studentLoginId")
                    or user_id
                ).strip()

                access_result = authenticate_study_access_detailed(student_id, login_id_used, server)
                access_data = access_result.get("data") if isinstance(access_result, dict) else None
                if not isinstance(access_data, dict):
                    access_data = {}
                access_api_result = access_data.get("result", {}) if isinstance(access_data.get("result", {}), dict) else {}

                child_auth_token = str(access_api_result.get("authToken", "")).strip()
                child_id = str(access_api_result.get("memId", "")).strip()
                mem_nm = str(access_api_result.get("memNm", "")).strip()

                if not access_result.get("ok") or not child_auth_token or not child_id:
                    fail_count += 1
                    ws.append([
                        tested_at, env_code, class_id, class_nm, target_age,
                        student_id, student_nm, login_id_used,
                        access_result.get("status_code"),
                        "FAIL", mem_nm, child_id,
                        access_result.get("error", "") or "study/access failed",
                    ])
                    style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, False, student_nm, mem_nm)
                    continue

                # 커리큘럼 API에서 year, month, week 조회
                cur_resp = get_curriculum_response(child_auth_token, child_id, server)
                if cur_resp is not None and cur_resp.ok:
                    cur_result = cur_resp.json().get("result", {})
                    year = datetime.now().year
                    month = cur_result.get("month")
                    week = cur_result.get("week")
                    curriculum_tp = int(cur_result.get("curriculumTp", 0))
                    child_age_from_class = cur_result.get("childAge", 0)
                else:
                    fail_count += 1
                    cur_status = cur_resp.status_code if cur_resp else None
                    cur_error = cur_resp.text if cur_resp else "curriculum response is None"
                    ws.append([
                        tested_at, env_code, class_id, class_nm, target_age,
                        student_id, student_nm, login_id_used,
                        cur_status, "FAIL", mem_nm, child_id,
                        f"curriculum failed: {cur_error}",
                    ])
                    style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, False, student_nm, mem_nm)
                    continue

                try:
                    report_resp = get_teacher_activity_report(
                        child_auth_token, child_id, child_age_from_class,
                        curriculum_tp, year, month, week, server,
                    )
                    if report_resp is not None:
                        http_status = report_resp.status_code
                        ok = report_resp.ok
                        error_msg = "" if ok else report_resp.text
                    else:
                        http_status = None
                        ok = False
                        error_msg = "teacherActivityReport response is None"
                except Exception as e:
                    http_status = None
                    ok = False
                    error_msg = str(e)

                if ok:
                    success_count += 1
                else:
                    fail_count += 1

                ws.append([
                    tested_at, env_code, class_id, class_nm, target_age,
                    student_id, student_nm, login_id_used,
                    http_status,
                    "PASS" if ok else "FAIL",
                    mem_nm, child_id, error_msg,
                ])
                style_api_row(ws, ws.max_row, _API_REPORT_HEADERS, ok, student_nm, mem_nm)

        save_api_report(wb, ws, report_path)
        print(
            f"[INFO] teacherActivityReport bulk completed. total={total_students}, "
            f"success={success_count}, fail={fail_count}"
        )

    except Exception as e:
        print(f"[ERROR] teacherActivityReport bulk exception: {e!r}")
        print(traceback.format_exc())


def worker_all_api_test(log_queue, user_id, user_pwd, server, device_label, steps,
                        gui_ctx=None):
    """단일 계정(첫 번째 학생)으로 steps에 포함된 API를 호출하고 엑셀을 생성한다."""
    import builtins
    import traceback
    import re as _re
    from datetime import datetime, date
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

    server_label = {"Prod": "Prod", "QA": "QA", "Dev": "Dev"}.get(server, server)

    match server:
        case "Prod":
            srv = "api"
        case "QA":
            srv = "qa-api"
        case "Dev":
            srv = "dev-api"
        case _:
            srv = "api"

    def _print_via_queue(*args, sep=" ", end="\n", **kwargs):
        msg = sep.join(str(a) for a in args) + end
        log_queue.put(msg.rstrip("\n"))

    builtins.print = _print_via_queue

    results = []  # (api_name, method, path, status, mark, result_data, error_detail)

    def _record(api_name, method, path, resp=None, error=None):
        if resp is not None:
            status = resp.status_code
            ok = resp.ok
            result_data = resp.text[:1000] if ok else ""
            error_detail = "" if ok else resp.text[:1000]
        elif error is not None:
            status = 0
            ok = False
            result_data = ""
            error_detail = str(error)
        else:
            status = 0
            ok = False
            result_data = ""
            error_detail = "unknown"
        mark = "PASS" if ok else "FAIL"
        results.append((api_name, method, path, status, mark, result_data, error_detail))
        print(f"  [{mark}] {method:6s} {path} -> {status} {error_detail[:120]}")

    # 공유 컨텍스트 (API 간 데이터 전달용)
    ctx = {"prod_id": "P0001", "ptnr_id": "1102"}

    try:
        print(f"[INFO] ALL API test started ({len(steps)}개)")

        # ── 로그인 & 반 정보 (공통 전처리) ──
        token = login_step1(user_id, user_pwd, srv)
        if not token:
            print("[ERROR] login failed.")
            return

        class_resp = class_list(token, user_id, srv)
        if class_resp is None:
            print("[ERROR] class list failed.")
            return

        classes = class_resp.json().get("result", {}).get("classList", [])
        if not classes:
            print("[ERROR] no classes found.")
            return

        first_class = classes[0]
        class_id = str(first_class.get("classId", ""))
        target_age = str(first_class.get("targetAge", ""))
        print(f"[INFO] class: {first_class.get('classNm')} ({class_id})")

        stu_resp = student_list_by_class(token, class_id, srv)
        if stu_resp is None:
            print("[ERROR] student list failed.")
            return

        students = stu_resp.json().get("result", {}).get("studentList", [])
        if not students:
            print("[ERROR] no students found.")
            return

        first_stu = students[0]
        student_id = str(first_stu.get("studentId", ""))
        print(f"[INFO] student: {first_stu.get('studentNm')} ({student_id})")

        # GUI에서 선택된 class/student 정보 반영
        _gui = gui_ctx or {}
        if _gui.get("class_nm"):
            first_class = {"classNm": _gui["class_nm"], "classId": _gui.get("class_id", ""), "targetAge": _gui.get("target_age", "")}
            class_id = _gui.get("class_id") or class_id
            target_age = _gui.get("target_age") or target_age
        if _gui.get("student_nm"):
            first_stu = {"studentNm": _gui["student_nm"], "studentId": _gui.get("student_id", "")}
            student_id = _gui.get("student_id") or student_id

        # study/access (child token 획득)
        print("\n=== 수업시작 (study/access) ===")
        try:
            access_result = authenticate_study_access_detailed(student_id, user_id, srv)
            access_data = access_result.get("data") if isinstance(access_result, dict) else None
            if not isinstance(access_data, dict):
                access_data = {}
            api_res = access_data.get("result", {}) if isinstance(access_data.get("result", {}), dict) else {}

            child_token = _gui.get("auth_token") or str(api_res.get("authToken", "")).strip()
            child_id = _gui.get("mem_id") or str(api_res.get("memId", "")).strip()

            if child_token:
                _record("수업시작", "POST", "/authenticate/study/access",
                        resp=type("R", (), {"status_code": 200, "ok": True, "text": str(access_data)[:1000]})())
            else:
                _record("수업시작", "POST", "/authenticate/study/access",
                        error="no child token in response")
                print("[ERROR] study/access failed. no child token.")
                return
        except Exception as e:
            _record("수업시작", "POST", "/authenticate/study/access", error=e)
            print(f"[ERROR] study/access exception: {e!r}")
            return

        print(f"[INFO] childToken: {child_token[:20]}..., childId: {child_id}")

        # report용 파라미터: 커리큘럼 API에서 조회
        curriculum_tp = 0
        child_age_int = 0
        year, month, week = 0, 0, 0

        cur_resp = get_curriculum_response(child_token, child_id, srv)
        if cur_resp is not None and cur_resp.ok:
            cur_result = cur_resp.json().get("result", {})
            year = date.today().year
            month = cur_result.get("month", 0)
            week = cur_result.get("week", 0)
            curriculum_tp = int(cur_result.get("curriculumTp", 0))
            child_age_int = cur_result.get("childAge", 0)
            print(f"[INFO] curriculum: year={year}, month={month}, week={week}")
        else:
            print(f"[WARN] curriculum API failed, report APIs may fail")

        # ── API 호출 함수 매핑 ──
        # 각 함수는 (display_name, method, path, response) 를 반환
        def _call_curriculum():
            resp = get_curriculum_response(child_token, child_id, srv)
            return ("커리큘럼 조회", "GET", "/witti-box/curriculum", resp)

        def _call_attendance_curriculum():
            resp = post_attendance_curriculum(child_token, srv)
            return ("출석 시간 전송", "POST", "/witti-app/attendance/curriculum", resp)

        def _call_witti_school_main():
            resp = get_witti_school_main(child_token, srv)
            # prodId, ptnrId 추출하여 ctx에 저장
            if resp is not None and resp.ok:
                sm = resp.json().get("result", {})
                pl = sm.get("prodList") or sm.get("productList") or []
                if pl:
                    ctx["prod_id"] = pl[0].get("prodId", ctx["prod_id"])
                    ctx["ptnr_id"] = str(pl[0].get("ptnrId", ctx["ptnr_id"]))
            return ("위티스쿨 메인", "GET", "/witti-school/main", resp)

        def _call_aram_bookworld_subject():
            resp = get_aram_bookworld_subject(child_token, ctx["ptnr_id"], ctx["prod_id"], srv)
            return ("아람북월드 과목", "GET", "/witti-school/aram-bookworld/subject", resp)

        def _call_ebook_main():
            resp = get_witti_school_ebook_main(child_token, srv)
            return ("도서관 메인", "GET", "/witti-school/e-book/main", resp)

        def _call_tv_main():
            resp = get_tv_main(child_token, srv)
            return ("위티TV 메인", "GET", "/tv/main", resp)

        def _call_teacher_activity_report():
            resp = get_teacher_activity_report(child_token, child_id, child_age_int, curriculum_tp, year, month, week, srv)
            return ("선생님 활동현황", "POST", "/report/teacherActivityReport", resp)

        def _call_parent_report():
            resp = get_parent_report(child_token, child_id, child_age_int, curriculum_tp, year, month, week, srv)
            return ("학습 리포트", "POST", "/report/parentReport", resp)

        # step 이름 → 호출 함수 매핑 (새 API 추가 시 여기만 추가)
        CALL_MAP = {
            "커리큘럼 조회 (curriculum)": _call_curriculum,
            "출석 시간 전송 (attendance/curriculum)": _call_attendance_curriculum,
            "위티스쿨 메인 (witti-school/main)": _call_witti_school_main,
            "아람북월드 과목 (aram-bookworld/subject)": _call_aram_bookworld_subject,
            "도서관 메인 (e-book/main)": _call_ebook_main,
            "위티TV 메인 (tv/main)": _call_tv_main,
            "선생님 활동현황 (report/teacherActivityReport)": _call_teacher_activity_report,
            "학습 리포트 > 부모(학생) / 주간 (report/parentReport)": _call_parent_report,
        }

        # ── steps 순회하며 API 호출 ──
        for step_name in steps:
            if step_name == "수업시작 (study/access)":
                continue  # 이미 위에서 처리됨

            call_fn = CALL_MAP.get(step_name)
            if call_fn is None:
                print(f"[WARN] ALL 매핑에 없는 API: {step_name}, skip")
                continue

            print(f"\n=== {step_name} ===")
            try:
                display_name, method, path, resp = call_fn()
                if resp is not None:
                    _record(display_name, method, path, resp=resp)
                else:
                    _record(display_name, method, path, error="API returned None")
            except Exception as e:
                # call_fn 내부에서 display_name을 알 수 없으므로 step_name 사용
                _record(step_name, "?", "?", error=e)

        # ── 결과 요약 ──
        pass_count = sum(1 for r in results if r[4] == "PASS")
        fail_count = sum(1 for r in results if r[4] == "FAIL")
        print(f"\n총 {len(results)}개 API | PASS: {pass_count} | FAIL: {fail_count}")

        # ── 엑셀 저장 ──
        date_str = datetime.now().strftime("%y%m%d")
        report_dir = os.path.join(os.getcwd(), "test_report", "api_test")
        os.makedirs(report_dir, exist_ok=True)
        file_path = os.path.join(report_dir, f"ALL_api_test_{date_str}.xlsx")

        if os.path.exists(file_path):
            wb = load_workbook(file_path)
        else:
            wb = Workbook()
            wb.remove(wb.active)

        time_str = datetime.now().strftime("%H-%M-%S")
        sheet_name = f"{user_id}_{time_str}"[:31]
        if sheet_name in wb.sheetnames:
            del wb[sheet_name]
        ws = wb.create_sheet(title=sheet_name)

        # 스타일
        header_font = Font(name="맑은 고딕", bold=True, size=11, color="FFFFFF")
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell_font = Font(name="맑은 고딕", size=10)
        center_align = Alignment(horizontal="center", vertical="center")
        cell_align = Alignment(vertical="center", wrap_text=True)
        pass_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
        fail_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
        pass_font = Font(name="맑은 고딕", size=10, color="006100", bold=True)
        fail_font = Font(name="맑은 고딕", size=10, color="9C0006", bold=True)
        thin_border = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin"),
        )

        # 요약 행
        ws.merge_cells("A1:I1")
        sc = ws["A1"]
        class_nm = first_class.get("classNm", "")
        student_nm = first_stu.get("studentNm", "")
        sc.value = (
            f"API 테스트 결과 — {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
            f"서버: {server_label}  |  계정: {user_id}  |  "
            f"반: {class_nm} ({class_id})  |  학생: {student_nm} ({student_id})  |  "
            f"총 {len(results)}개  |  PASS: {pass_count}  |  FAIL: {fail_count}"
        )
        sc.font = Font(name="맑은 고딕", bold=True, size=12)
        sc.alignment = Alignment(vertical="center")
        ws.row_dimensions[1].height = 30

        # 헤더
        col_headers = ["No.", "서버", "카테고리", "Method", "API Path", "Status", "결과", "Result Data", "에러 상세"]
        ws.append([])
        for ci, h in enumerate(col_headers, 1):
            c = ws.cell(row=3, column=ci, value=h)
            c.font = header_font
            c.fill = header_fill
            c.alignment = header_align
            c.border = thin_border
        ws.row_dimensions[3].height = 25

        # 데이터
        for i, (tag, method, path, status, mark, rd, ed) in enumerate(results, 1):
            row = i + 3
            vals = [i, server_label, tag, method, path, status if status else "", mark, rd, ed]
            for ci, v in enumerate(vals, 1):
                c = ws.cell(row=row, column=ci, value=v)
                c.font = cell_font
                c.border = thin_border
                c.alignment = center_align if ci in (1, 2, 4, 6, 7) else cell_align

            rc = ws.cell(row=row, column=7)
            if mark == "PASS":
                rc.fill = pass_fill
                rc.font = pass_font
            else:
                rc.fill = fail_fill
                rc.font = fail_font

        # 카테고리 배경색 교대
        tag_colors = {}
        color_toggle = ["F2F7FB", "FFFFFF"]
        cidx = 0
        prev_tag = None
        for i, (tag, *_) in enumerate(results):
            if tag != prev_tag:
                if tag not in tag_colors:
                    tag_colors[tag] = color_toggle[cidx % 2]
                    cidx += 1
                prev_tag = tag
            row = i + 4
            bg = PatternFill(start_color=tag_colors[tag], end_color=tag_colors[tag], fill_type="solid")
            for col in range(1, 8):
                c = ws.cell(row=row, column=col)
                if col != 7:
                    c.fill = bg

        ws.column_dimensions["A"].width = 6
        ws.column_dimensions["B"].width = 9
        ws.column_dimensions["C"].width = 16
        ws.column_dimensions["D"].width = 9
        ws.column_dimensions["E"].width = 48
        ws.column_dimensions["F"].width = 9
        ws.column_dimensions["G"].width = 9
        ws.column_dimensions["H"].width = 60
        ws.column_dimensions["I"].width = 60

        ws.auto_filter.ref = f"A3:I{len(results) + 3}"
        ws.freeze_panes = "A4"

        wb.save(file_path)
        print(f"[INFO] 엑셀 저장 완료: {file_path} (탭: {sheet_name})")

    except Exception as e:
        print(f"[ERROR] ALL API test exception: {e!r}")
        print(traceback.format_exc())


def worker_api_pipeline(log_queue, user_id, user_pwd, server, device_label, steps,
                        gui_ctx=None):
    """우측 리스트의 API들을 순서대로 각각 독립 실행하여 개별 보고서를 생성한다."""
    import builtins

    def _print_via_queue(*args, sep=" ", end="\n", **kwargs):
        msg = sep.join(str(a) for a in args) + end
        log_queue.put(msg.rstrip("\n"))

    builtins.print = _print_via_queue

    print(f"[INFO] API pipeline started: {len(steps)}개 API 순차 실행")

    # API 이름 → 기존 worker 함수 매핑
    WORKER_MAP = {
        "수업시작 (study/access)": worker_study_access_bulk,
        "커리큘럼 조회 (curriculum)": worker_curriculum_bulk,
        "출석 시간 전송 (attendance/curriculum)": worker_attendance_curriculum_bulk,
        "위티스쿨 메인 (witti-school/main)": worker_witti_school_main_bulk,
        "아람북월드 과목 (aram-bookworld/subject)": worker_aram_bookworld_subject_bulk,
        "도서관 메인 (e-book/main)": worker_ebook_main_bulk,
        "위티TV 메인 (tv/main)": worker_tv_main_bulk,
        "선생님 활동현황 (report/teacherActivityReport)": worker_teacher_activity_report_bulk,
        "학습 리포트 > 부모(학생) / 주간 (report/parentReport)": worker_parent_report_bulk,
    }

    # ALL 선택 시 단일 계정 전체 API 테스트
    if "ALL" in steps:
        all_steps = [k for k in WORKER_MAP.keys()]
        print(f"[INFO] ALL 모드: 단일 계정 전체 API 테스트 실행 ({len(all_steps)}개)")
        worker_all_api_test(log_queue, user_id, user_pwd, server, device_label, all_steps,
                            gui_ctx=gui_ctx)
        return

    for idx, step_name in enumerate(steps, 1):
        print(f"\n{'='*50}")
        print(f"[{idx}/{len(steps)}] {step_name} 실행 시작")
        print(f"{'='*50}")

        worker_fn = WORKER_MAP.get(step_name)
        if worker_fn is None:
            print(f"[ERROR] 알 수 없는 API: {step_name}")
            continue

        # 기존 worker를 직접 호출 (같은 프로세스 내에서 순차 실행)
        worker_fn(log_queue, user_id, user_pwd, server, device_label)

    print(f"\n[INFO] 모든 API 실행 완료 ({len(steps)}개)")


if getattr(sys, "frozen", False):
    import __main__
    __main__.worker_main = worker_main
#     __main__.worker_complete_missions = worker_complete_missions
    __main__.worker_study_access_bulk = worker_study_access_bulk
    __main__.worker_curriculum_bulk = worker_curriculum_bulk
    __main__.worker_attendance_curriculum_bulk = worker_attendance_curriculum_bulk
    __main__.worker_witti_school_main_bulk = worker_witti_school_main_bulk
    __main__.worker_aram_bookworld_subject_bulk = worker_aram_bookworld_subject_bulk
    __main__.worker_ebook_main_bulk = worker_ebook_main_bulk
    __main__.worker_tv_main_bulk = worker_tv_main_bulk
    __main__.worker_teacher_activity_report_bulk = worker_teacher_activity_report_bulk
    __main__.worker_parent_report_bulk = worker_parent_report_bulk
    __main__.worker_all_api_test = worker_all_api_test
    __main__.worker_api_pipeline = worker_api_pipeline
    print("Registered workers on __main__")


class MainApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.log_queue: Queue = None
        self.worker_process: Process = None
        self._drain_timer: QtCore.QTimer = None

        class EmittingStream(QtCore.QObject):
            textWritten = QtCore.pyqtSignal(str)
            def write(self, text):
                if not text or text == "\n": return
                self.textWritten.emit(text)
            def flush(self): pass
        self.stdout_stream = EmittingStream()
        sys.stdout = self.stdout_stream
        sys.stderr = self.stdout_stream
        self.stdout_stream.textWritten.connect(self.append_log)

        logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
        self.logger = logging.getLogger(__name__)

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
        ensure_adb_server()
        self.load_devices()

        self.ui.listView_2.setGeometry(QtCore.QRect(10, 20, 301, 352))
        self.label_mem_id = QtWidgets.QLabel(self.ui.groupBox_11)
        self.label_mem_id.setGeometry(QtCore.QRect(10, 379, 301, 24))
        self.label_mem_id.setObjectName("label_mem_id")
        self.label_mem_id.setText("memId: -")
        self.label_auth_token = QtWidgets.QLabel(self.ui.groupBox_11)
        self.label_auth_token.setGeometry(QtCore.QRect(10, 407, 301, 24))
        self.label_auth_token.setObjectName("label_auth_token")
        self.label_auth_token.setText("authToken: -")

        self.class_list_data = []
        self.class_auth_token = None
        self.class_api_server = None
        self.study_access_mem_nm = None
        self.study_access_mem_id = None
        self.study_access_auth_token = None
        self.selected_class_nm = None
        self.selected_class_id = None
        self.selected_target_age = None
        self.selected_student_nm = None
        self.selected_student_id = None
        self.class_list_model = QtGui.QStandardItemModel(self)
        self.student_list_model = QtGui.QStandardItemModel(self)
        self.ui.listView.setModel(self.class_list_model)
        self.ui.listView.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.ui.listView_2.setModel(self.student_list_model)
        self.ui.listView_2.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        self.ui.comboBox.setItemData(1, 0, QtCore.Qt.UserRole)   # ALL
        self.ui.comboBox.setItemData(2, 1, QtCore.Qt.UserRole)   # 한글
        self.ui.comboBox.setItemData(3, 2, QtCore.Qt.UserRole)   # 수학
        self.ui.comboBox.setItemData(4, 3, QtCore.Qt.UserRole)   # 창의
        self.ui.lineEdit.setText("MGtest000")
        self.ui.lineEdit_2.setText("mini1122@@")

        self.ui.pushButton.clicked.connect(self.close)
        self.ui.pushButton_2.clicked.connect(self.open_report_folder)
        self.ui.pushButton_3.clicked.connect(self.on_start)
        self.ui.pushButton_4.clicked.connect(self.on_stop)
        self.ui.pushButton_5.clicked.connect(self.on_start)
        self.ui.pushButton_6.clicked.connect(self.load_devices)
        self.ui.pushButton_7.clicked.connect(self.on_start)
        self.ui.pushButton_8.clicked.connect(self.clear_log)
        self.ui.pushButton_10.clicked.connect(self.on_load_class_list)
        self.ui.listView.clicked.connect(self.on_class_item_clicked)
        self.ui.listView_2.clicked.connect(self.on_student_item_clicked)

        # ── API pipeline tab setup ──
        self._init_api_pipeline_tab()
        self.ui.pushButton_api_add.clicked.connect(self._api_pipeline_add)
        self.ui.pushButton_api_remove.clicked.connect(self._api_pipeline_remove)
        self.ui.listWidget_api_available.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.ui.listWidget_api_pipeline.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.ui.listWidget_api_available.doubleClicked.connect(self._api_pipeline_add)
        self.ui.listWidget_api_pipeline.doubleClicked.connect(self._api_pipeline_remove)
        self.ui.pushButton_api_run.clicked.connect(self.on_run_api_pipeline)

    def open_report_folder(self):
        project_dir = os.path.abspath(os.getcwd())
        report_dir  = os.path.join(project_dir, "test_report")
        if not os.path.isdir(report_dir):
            try:
                os.makedirs(report_dir, exist_ok=True)
            except Exception as e:
                self.logger.error(f"폴더 생성 실패: {e!r}")
                return
        QDesktopServices.openUrl(QUrl.fromLocalFile(report_dir))

    @QtCore.pyqtSlot()
    def clear_log(self):
        self.ui.plainTextEdit.clear()

    @QtCore.pyqtSlot(str)
    def append_log(self, text):
        edit = self.ui.plainTextEdit
        edit.appendPlainText(text.rstrip("\n"))
        edit.verticalScrollBar().setValue(edit.verticalScrollBar().maximum())

    @staticmethod
    def _resolve_api_server(server_name):
        mapping = {
            "Prod": "api",
            "QA": "qa-api",
            "Dev": "dev-api",
        }
        return mapping.get(server_name, "api")

    def on_load_class_list(self):
        input_id = self.ui.lineEdit.text().strip()
        input_pwd = self.ui.lineEdit_2.text().strip()
        server_name = self.ui.comboBox_6.currentText()
        api_server = self._resolve_api_server(server_name)

        if not input_id or not input_pwd:
            self.logger.error("Class List 조회를 위해 ID/PW를 입력해주세요.")
            return

        auth_token = login_step1(input_id, input_pwd, api_server)
        if not auth_token:
            self.logger.error("Class List 조회 실패: 로그인(authToken 발급) 실패")
            return
        self.class_auth_token = auth_token
        self.class_api_server = api_server

        response = class_list(auth_token, input_id, api_server)
        if response is None:
            self.logger.error("Class List 조회 실패: API 응답 없음")
            return

        try:
            data = response.json()
            classes = data.get("result", {}).get("classList", [])
            self.class_list_data = classes

            self.class_list_model.clear()
            self.student_list_model.clear()
            for cls in classes:
                class_nm = str(cls.get("classNm", "")).strip() or "-"
                target_age = str(cls.get("targetAge", "")).strip() or "-"
                class_id = str(cls.get("classId", "")).strip()
                item = QtGui.QStandardItem(f"{class_nm} / {target_age}")
                item.setData(class_id, QtCore.Qt.UserRole)
                self.class_list_model.appendRow(item)

            self.logger.info(f"Class List {len(classes)}건 로드 완료")
            self._auto_select_first_class_and_student()
        except Exception as e:
            self.logger.error(f"Class List 파싱 실패: {e!r}")

    def _auto_select_first_class_and_student(self):
        if self.class_list_model.rowCount() <= 0:
            self.logger.warning("Auto select skipped: class list is empty.")
            return

        first_class_index = self.class_list_model.index(0, 0)
        if not first_class_index.isValid():
            self.logger.warning("Auto select skipped: invalid first class index.")
            return

        self.ui.listView.setCurrentIndex(first_class_index)
        self.on_class_item_clicked(first_class_index)

        if self.student_list_model.rowCount() <= 0:
            self.logger.warning("Auto select skipped: student list is empty.")
            return

        first_student_index = self.student_list_model.index(0, 0)
        if not first_student_index.isValid():
            self.logger.warning("Auto select skipped: invalid first student index.")
            return

        self.ui.listView_2.setCurrentIndex(first_student_index)
        self.on_student_item_clicked(first_student_index)
        self.logger.info("Auto-selected first class and first student.")

    def on_class_item_clicked(self, index):
        class_id = index.data(QtCore.Qt.UserRole)
        if not class_id:
            self.logger.warning("선택한 클래스의 classId를 찾을 수 없습니다.")
            return
        # 선택된 class 정보 저장
        self.selected_class_id = class_id
        display = index.data(QtCore.Qt.DisplayRole) or ""
        self.selected_class_nm = display.split(" / ")[0] if " / " in display else display
        self.selected_target_age = display.split(" / ")[1] if " / " in display else ""
        if not self.class_auth_token or not self.class_api_server:
            self.logger.error("학생 목록 조회 실패: authToken/server 정보가 없습니다. 먼저 Class List를 조회해주세요.")
            return

        response = student_list_by_class(self.class_auth_token, class_id, self.class_api_server)
        if response is None:
            self.logger.error("학생 목록 조회 실패: API 응답 없음")
            return

        try:
            data = response.json()
            students = data.get("result", {}).get("studentList", [])
            students = sorted(
                students,
                key=lambda s: str(s.get("studentNm", "")).strip(),
            )

            self.student_list_model.clear()
            for student in students:
                student_nm = str(student.get("studentNm", "")).strip() or "-"
                student_id = str(student.get("studentId", "")).strip()
                item = QtGui.QStandardItem(student_nm)
                item.setData(student_id, QtCore.Qt.UserRole)
                item.setData(student, QtCore.Qt.UserRole + 1)
                self.student_list_model.appendRow(item)

            self.logger.info(f"Student List {len(students)}건 로드 완료 (classId={class_id})")
        except Exception as e:
            self.logger.error(f"Student List 파싱 실패: {e!r}")

    def on_student_item_clicked(self, index):
        student_id = str(index.data(QtCore.Qt.UserRole) or "").strip()
        student_data = index.data(QtCore.Qt.UserRole + 1) or {}
        login_id = str(
            student_data.get("loginId")
            or student_data.get("studentLoginId")
            or self.ui.lineEdit.text().strip()
        ).strip()

        if not student_id:
            self.logger.warning("선택한 학생의 studentId를 찾을 수 없습니다.")
            return
        # 선택된 student 정보 저장
        self.selected_student_id = student_id
        self.selected_student_nm = str(student_data.get("studentNm", "")).strip()
        if not login_id:
            self.logger.error("study/access 호출 실패: loginId를 찾을 수 없습니다.")
            return

        server_name = self.ui.comboBox_6.currentText()
        api_server = self._resolve_api_server(server_name)
        response = authenticate_study_access(student_id, login_id, api_server)
        if response is None:
            self.logger.error(
                f"study/access 호출 실패: studentId={student_id}, loginId={login_id}, "
                f"studentKeys={list(student_data.keys()) if isinstance(student_data, dict) else 'N/A'}"
            )
            return

        mem_nm, mem_id, auth_token = get_study_access_auth()
        self.study_access_mem_nm = mem_nm
        self.study_access_mem_id = mem_id
        self.study_access_auth_token = auth_token
        token_masked = f"{auth_token[:12]}..." if auth_token else "None"
        self.label_mem_id.setText(f"memId: {mem_id if mem_id else '-'}")
        self.label_auth_token.setText(f"authToken: {token_masked}")
        self.logger.info(
            f"study/access 완료 (studentId={student_id}, memId={mem_id}, authToken={token_masked})"
        )

    def load_devices(self):
        DEVICE_ALIASES = {
            "R9TX202G5NK": "Galaxy Tab A9+ / AOS 15",
            "R54Y600EM7T": "Galaxy Tab S10 FE / AOS 15",
            "R9TX20A57VM": "Galaxy Tab A9+ / AOS 13"
        }
        try:
            out = run_adb(["devices", "-l"], text=True, encoding="utf-8", errors="ignore", timeout=20)
            lines = [ln for ln in out.strip().splitlines()[1:] if ln.strip()]
            entries = []
            for ln in lines:
                parts = ln.split()
                if len(parts) < 2 or parts[1] != "device": continue
                dev_id = parts[0]
                model = next((p.split(":", 1)[1] for p in parts if p.startswith("model:")), "").replace("_", "-")
                wifi = False
                serial_hint = ""
                m = re.search(r"^adb-([A-Za-z0-9]+)-", dev_id)
                if m and "._adb-tls-connect._tcp" in dev_id:
                    serial_hint = m.group(1)
                    wifi = True
                elif ":" in dev_id and dev_id.rsplit(":", 1)[1].isdigit():
                    wifi = True
                if serial_hint: canon = serial_hint
                else:
                    try: canon = run_adb(["-s", dev_id, "get-serialno"], text=True, timeout=3).strip()
                    except Exception: canon = dev_id
                entries.append({"dev_id": dev_id, "model": model, "wifi": wifi, "canon": canon})

            by_serial = {}
            for e in entries:
                k = e["canon"]
                by_serial.setdefault(k, {})
                by_serial[k]['wifi' if e['wifi'] else 'usb'] = e

            items = []
            for k, d in by_serial.items():
                display_name = DEVICE_ALIASES.get(k, k)
                if 'usb' in d: items.append((f"{display_name} [USB]", d['usb']['canon']))
                if 'wifi' in d: items.append((f"{display_name} [Wi-Fi]", d['wifi']['dev_id']))
            if not items: items = [("(no devices)", "")]
        except Exception as e:
            items = [(f"Error: {e}", "")]

        self.ui.comboBox_4.clear()
        for label, dev_id in items:
            self.ui.comboBox_4.addItem(label, dev_id)

    def on_start(self):
        if self.worker_process and self.worker_process.is_alive():
            self.logger.warning("작업이 이미 실행 중입니다.")
            return

        device_name = self.ui.comboBox_4.currentData()
        device_label = self.ui.comboBox_4.currentText()
        inputId     = self.ui.lineEdit.text().strip()
        inputPwd    = self.ui.lineEdit_2.text().strip()
        subjCd      = self.ui.comboBox.currentData()
        itemCd      = self.ui.comboBox_2.currentIndex()
        curtnSeq    = self.ui.comboBox_3.currentIndex()
        btn_name    = self.sender().objectName()
        title_name  = self.ui.comboBox_5.currentText()
        server      = self.ui.comboBox_6.currentText()

        if not inputId or not inputPwd:
            self.logger.error("ID와 PWD를 모두 입력해주세요.")
            return
        if btn_name == "pushButton_3" and (self.ui.comboBox.currentIndex()==0 or self.ui.comboBox_2.currentIndex()==0 or self.ui.comboBox_3.currentIndex()==0):
            self.logger.error("과목, STEP, 호를 모두 선택해주세요.")
            return
        if btn_name == "pushButton_7" and self.ui.comboBox_5.currentIndex()==0:
            self.logger.error("Song을 선택해주세요.")
            return
        if btn_name in {"pushButton_5", "pushButton_3", "pushButton_7"} and not self.study_access_auth_token:
            self.logger.error("study/access authToken이 없습니다. 먼저 학생을 선택해주세요.")
            return

        self.log_queue = Queue()
        args = (
            self.log_queue,
            btn_name,
            device_name,
            device_label,
            inputId,
            inputPwd,
            subjCd,
            itemCd,
            curtnSeq,
            title_name,
            server,
            self.study_access_mem_nm,
            self.study_access_mem_id,
            self.study_access_auth_token,
        )
        self.worker_process = Process(target=worker_main, args=args)
        self.worker_process.start()
        self.logger.info(f"AutoTest 프로세스 시작 (PID={self.worker_process.pid})")

        if self._drain_timer is None:
            self._drain_timer = QtCore.QTimer(self)
            self._drain_timer.timeout.connect(self._drain_logs)
        self._drain_timer.start(100)

#     def on_complete_missions(self):
#         if self.worker_process and self.worker_process.is_alive():
#             self.logger.warning("작업이 이미 실행 중입니다.")
#             return
# 
#         user_id = self.ui.lineEdit.text().strip()
#         user_pwd = self.ui.lineEdit_2.text().strip()
#         server = self.ui.comboBox_6.currentText()
# 
#         if not all([user_id, user_pwd, server]):
#             msg_box = QMessageBox()
#             msg_box.setIcon(QMessageBox.Warning)
#             msg_box.setText("ID, PW, 서버를 모두 입력해주세요.")
#             msg_box.setWindowTitle("입력 오류")
#             msg_box.exec_()
#             return
# 
#         self.log_queue = Queue()
#         args = (self.log_queue, user_id, user_pwd, server)
#         self.worker_process = Process(target=worker_complete_missions, args=args)
#         self.worker_process.start()
#         self.logger.info(f"미션 완료 프로세스 시작 (PID={self.worker_process.pid})")
# 
#         if self._drain_timer is None:
#             self._drain_timer = QtCore.QTimer(self)
#             self._drain_timer.timeout.connect(self._drain_logs)
#         self._drain_timer.start(100)
# 
    # ── API pipeline helpers ───────────────────────────────────────────
    API_STEPS = [
        "ALL",
        "수업시작 (study/access)",
        "커리큘럼 조회 (curriculum)",
        "출석 시간 전송 (attendance/curriculum)",
        "위티스쿨 메인 (witti-school/main)",
        "아람북월드 과목 (aram-bookworld/subject)",
        "도서관 메인 (e-book/main)",
        "위티TV 메인 (tv/main)",
        "선생님 활동현황 (report/teacherActivityReport)",
        "학습 리포트 > 부모(학생) / 주간 (report/parentReport)",
    ]

    def _init_api_pipeline_tab(self):
        """좌측 API 목록 리스트에 사용 가능한 API 항목을 채운다."""
        for name in self.API_STEPS:
            self.ui.listWidget_api_available.addItem(name)

    def _api_pipeline_add(self):
        """좌측에서 선택한 API를 우측 리스트에 추가 (중복 불가)."""
        item = self.ui.listWidget_api_available.currentItem()
        if item is None:
            return
        name = item.text()

        # ALL이 이미 있으면 다른 항목 추가 불가
        for i in range(self.ui.listWidget_api_pipeline.count()):
            existing = self.ui.listWidget_api_pipeline.item(i).text().split(". ", 1)[-1]
            if existing == "ALL" and name != "ALL":
                return
        # ALL을 추가하면 기존 항목 모두 비우고 ALL만 남김
        if name == "ALL":
            self.ui.listWidget_api_pipeline.clear()
            self.ui.listWidget_api_pipeline.addItem("1. ALL")
            return

        # 중복 체크
        for i in range(self.ui.listWidget_api_pipeline.count()):
            existing = self.ui.listWidget_api_pipeline.item(i).text()
            if existing.split(". ", 1)[-1] == name:
                return
        idx = self.ui.listWidget_api_pipeline.count() + 1
        self.ui.listWidget_api_pipeline.addItem(f"{idx}. {name}")

    def _api_pipeline_remove(self):
        """우측 파이프라인 리스트에서 선택 항목을 제거하고 번호 재정렬."""
        row = self.ui.listWidget_api_pipeline.currentRow()
        if row < 0:
            return
        self.ui.listWidget_api_pipeline.takeItem(row)
        # 번호 재정렬
        for i in range(self.ui.listWidget_api_pipeline.count()):
            text = self.ui.listWidget_api_pipeline.item(i).text()
            # "N. 실제이름" → "새번호. 실제이름"
            name = text.split(". ", 1)[-1]
            self.ui.listWidget_api_pipeline.item(i).setText(f"{i + 1}. {name}")

    def _get_pipeline_steps(self):
        """우측 리스트에서 API 이름만 순서대로 추출."""
        steps = []
        for i in range(self.ui.listWidget_api_pipeline.count()):
            text = self.ui.listWidget_api_pipeline.item(i).text()
            name = text.split(". ", 1)[-1]
            steps.append(name)
        return steps

    def on_run_api_pipeline(self):
        """파이프라인 실행 버튼 클릭 핸들러."""
        if self.worker_process and self.worker_process.is_alive():
            self.logger.warning("작업이 이미 실행 중입니다.")
            return

        steps = self._get_pipeline_steps()
        if not steps:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText("실행할 API를 파이프라인에 추가해주세요.")
            msg_box.setWindowTitle("파이프라인 비어있음")
            msg_box.exec_()
            return

        user_id = self.ui.lineEdit.text().strip()
        user_pwd = self.ui.lineEdit_2.text().strip()
        server = self.ui.comboBox_6.currentText()

        if not all([user_id, user_pwd, server]):
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText("ID, PW, 서버를 모두 입력해주세요.")
            msg_box.setWindowTitle("입력 오류")
            msg_box.exec_()
            return

        self.log_queue = Queue()
        device_label = self.ui.comboBox_4.currentText()
        gui_ctx = {
            "auth_token": self.study_access_auth_token,
            "mem_id": self.study_access_mem_id,
            "class_nm": self.selected_class_nm,
            "class_id": self.selected_class_id,
            "target_age": self.selected_target_age,
            "student_nm": self.selected_student_nm,
            "student_id": self.selected_student_id,
        }
        args = (self.log_queue, user_id, user_pwd, server, device_label, steps, gui_ctx)
        self.worker_process = Process(target=worker_api_pipeline, args=args)
        self.worker_process.start()
        self.logger.info(f"API pipeline 프로세스 시작 (PID={self.worker_process.pid}), steps={steps}")

        if self._drain_timer is None:
            self._drain_timer = QtCore.QTimer(self)
            self._drain_timer.timeout.connect(self._drain_logs)
        self._drain_timer.start(100)

    def on_run_study_access_bulk(self):
        if self.worker_process and self.worker_process.is_alive():
            self.logger.warning("작업이 이미 실행 중입니다.")
            return

        user_id = self.ui.lineEdit.text().strip()
        user_pwd = self.ui.lineEdit_2.text().strip()
        server = self.ui.comboBox_6.currentText()

        if not all([user_id, user_pwd, server]):
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText("ID, PW, 서버를 모두 입력해주세요.")
            msg_box.setWindowTitle("입력 오류")
            msg_box.exec_()
            return

        self.log_queue = Queue()
        device_label = self.ui.comboBox_4.currentText()
        args = (self.log_queue, user_id, user_pwd, server, device_label)
        self.worker_process = Process(target=worker_study_access_bulk, args=args)
        self.worker_process.start()
        self.logger.info(f"study/access bulk 프로세스 시작 (PID={self.worker_process.pid})")

        if self._drain_timer is None:
            self._drain_timer = QtCore.QTimer(self)
            self._drain_timer.timeout.connect(self._drain_logs)
        self._drain_timer.start(100)

    def on_run_curriculum_bulk(self):
        if self.worker_process and self.worker_process.is_alive():
            self.logger.warning("작업이 이미 실행 중입니다.")
            return

        user_id = self.ui.lineEdit.text().strip()
        user_pwd = self.ui.lineEdit_2.text().strip()
        server = self.ui.comboBox_6.currentText()

        if not all([user_id, user_pwd, server]):
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setText("ID, PW, 서버를 모두 입력해주세요.")
            msg_box.setWindowTitle("입력 오류")
            msg_box.exec_()
            return

        self.log_queue = Queue()
        device_label = self.ui.comboBox_4.currentText()
        args = (self.log_queue, user_id, user_pwd, server, device_label)
        self.worker_process = Process(target=worker_curriculum_bulk, args=args)
        self.worker_process.start()
        self.logger.info(f"curriculum bulk 프로세스 시작 (PID={self.worker_process.pid})")

        if self._drain_timer is None:
            self._drain_timer = QtCore.QTimer(self)
            self._drain_timer.timeout.connect(self._drain_logs)
        self._drain_timer.start(100)

    def _drain_logs(self):
        if not self.log_queue: return
        while not self.log_queue.empty():
            try:
                line = self.log_queue.get_nowait()
                self.append_log(line)
            except Exception:
                break

    def on_stop(self):
        if self.worker_process and self.worker_process.is_alive():
            self.worker_process.terminate()
            self.worker_process.join(1)
            self.logger.info("작업 프로세스가 중단되었습니다.")
        else:
            self.logger.info("실행 중인 작업이 없습니다.")
        if self._drain_timer:
            self._drain_timer.stop()


def main():
    app = QApplication(sys.argv)
    window = MainApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    freeze_support()
    main()
