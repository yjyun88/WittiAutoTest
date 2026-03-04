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
    get_study_access_auth,
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
    inputId,
    inputPwd,
    subjCd,
    itemCd,
    curtnSeq,
    title_name,
    server,
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
            inputId,
            inputPwd,
            subjCd,
            itemCd,
            curtnSeq,
            title_name,
            server,
            study_access_auth_token,
        )
    except Exception as e:
        print(f"[ERROR] AutoTest_Start 중 예외: {e!r}")
        print(traceback.format_exc())

def worker_complete_missions(log_queue, user_id, user_pwd, server):
    match server:
        case "Prod":
            server = "api"
        case "QA":
            server = "qa-api"
        case "Dev":
            server = "dev-api"
        case "Total-Test":
            server = "total-test-api"

    import builtins, traceback
    def _print_via_queue(*args, sep=" ", end="\n", **kwargs):
        msg = sep.join(str(a) for a in args) + end
        log_queue.put(msg.rstrip("\n"))
    builtins.print = _print_via_queue

    try:
        print("오늘의 미션 완료 처리를 시작합니다...")

        refreshToken, childIds, childNms = login_step1(user_id, user_pwd, server)
        if not refreshToken:
            print("[ERROR] 1차 로그인 실패. ID/PW나 서버 설정을 확인하세요.")
            return

        if not childIds:
            print("[INFO] 학습을 진행할 자녀 정보가 없습니다.")
            return

        auth_tokens_by_child = login_step2_for_all_children(refreshToken, childIds, server)
        if not auth_tokens_by_child:
            print("[ERROR] 2차 로그인 실패: 모든 자녀의 토큰을 발급받지 못했습니다.")
            return

        all_child_missions = []

        for child_id, child_name in zip(childIds, childNms):
            child_specific_auth_token = auth_tokens_by_child.get(child_id)
            if not child_specific_auth_token:
                print(f"[WARN] '{child_name}'({child_id})의 2차 로그인 토큰을 찾을 수 없습니다. 이 자녀의 미션을 건너뜁니다.")
                continue
            
            response = get_curriculum_response(child_specific_auth_token, child_id, server)

            if response is None:
                print(f"[WARN] '{child_name}'의 커리큘럼 조회 실패. 다음 자녀로 넘어갑니다.")
                continue

            try:
                data = response.json()
                mission_list = data.get("result", {}).get("missionList", [])

                if not mission_list:
                    print(f"[INFO] '{child_name}'에게 할당된 오늘의 미션이 없습니다.")
                    continue

                for mission in mission_list:
                    mission['childNm'] = child_name
                    mission['childId'] = child_id
                    all_child_missions.append(mission)

            except Exception as e:
                print(f"[ERROR] '{child_name}'의 커리큘럼 응답 파싱 중 오류 발생: {e}")
                continue

        complete_today_missions(auth_tokens_by_child, all_child_missions, server)

        print("\n오늘의 미션 완료 처리가 성공적으로 종료되었습니다.")

    except Exception as e:
        print(f"[ERROR] 미션 완료 처리 중 예외 발생: {e!r}")
        print(traceback.format_exc())


if getattr(sys, "frozen", False):
    import __main__
    __main__.worker_main = worker_main
    __main__.worker_complete_missions = worker_complete_missions
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

        self.ui.listView_2.setGeometry(QtCore.QRect(20, 20, 341, 275))
        self.label_mem_id = QtWidgets.QLabel(self.ui.groupBox_11)
        self.label_mem_id.setGeometry(QtCore.QRect(20, 302, 341, 24))
        self.label_mem_id.setObjectName("label_mem_id")
        self.label_mem_id.setText("memId: -")
        self.label_auth_token = QtWidgets.QLabel(self.ui.groupBox_11)
        self.label_auth_token.setGeometry(QtCore.QRect(20, 330, 341, 24))
        self.label_auth_token.setObjectName("label_auth_token")
        self.label_auth_token.setText("authToken: -")

        self.class_list_data = []
        self.class_auth_token = None
        self.class_api_server = None
        self.study_access_mem_id = None
        self.study_access_auth_token = None
        self.class_list_model = QtGui.QStandardItemModel(self)
        self.student_list_model = QtGui.QStandardItemModel(self)
        self.ui.listView.setModel(self.class_list_model)
        self.ui.listView_2.setModel(self.student_list_model)

        self.ui.comboBox.setItemData(1, 1, QtCore.Qt.UserRole)
        self.ui.comboBox.setItemData(2, 2, QtCore.Qt.UserRole)
        self.ui.comboBox.setItemData(3, 3, QtCore.Qt.UserRole)
        self.ui.lineEdit.setText("MGsales001")
        self.ui.lineEdit_2.setText("mini1122@@")

        self.ui.pushButton.clicked.connect(self.close)
        self.ui.pushButton_2.clicked.connect(self.on_start)
        self.ui.pushButton_3.clicked.connect(self.on_start)
        self.ui.pushButton_4.clicked.connect(self.on_stop)
        self.ui.pushButton_5.clicked.connect(self.open_report_folder)
        self.ui.pushButton_6.clicked.connect(self.load_devices)
        self.ui.pushButton_7.clicked.connect(self.on_start)
        self.ui.pushButton_8.clicked.connect(self.clear_log)
        self.ui.pushButton_10.clicked.connect(self.on_load_class_list)
        self.ui.listView.clicked.connect(self.on_class_item_clicked)
        self.ui.listView_2.clicked.connect(self.on_student_item_clicked)
        self.ui.pushButton_9.clicked.connect(self.on_complete_missions)

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
            "Total-Test": "total-test-api",
        }
        return mapping.get(server_name, server_name)

    def on_load_class_list(self):
        input_id = self.ui.lineEdit.text().strip()
        input_pwd = self.ui.lineEdit_2.text().strip()
        server_name = self.ui.comboBox_6.currentText()
        api_server = self._resolve_api_server(server_name)

        if not input_id or not input_pwd:
            self.logger.error("Class List 조회를 위해 ID/PW를 입력해주세요.")
            return

        auth_token, _, _ = login_step1(input_id, input_pwd, api_server)
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
        except Exception as e:
            self.logger.error(f"Class List 파싱 실패: {e!r}")

    def on_class_item_clicked(self, index):
        class_id = index.data(QtCore.Qt.UserRole)
        if not class_id:
            self.logger.warning("선택한 클래스의 classId를 찾을 수 없습니다.")
            return
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

        _, mem_id, auth_token = get_study_access_auth()
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
        if btn_name in {"pushButton_2", "pushButton_3", "pushButton_7"} and not self.study_access_auth_token:
            self.logger.error("study/access authToken이 없습니다. 먼저 학생을 선택해주세요.")
            return

        self.log_queue = Queue()
        args = (
            self.log_queue,
            btn_name,
            device_name,
            inputId,
            inputPwd,
            subjCd,
            itemCd,
            curtnSeq,
            title_name,
            server,
            self.study_access_auth_token,
        )
        self.worker_process = Process(target=worker_main, args=args)
        self.worker_process.start()
        self.logger.info(f"AutoTest 프로세스 시작 (PID={self.worker_process.pid})")

        if self._drain_timer is None:
            self._drain_timer = QtCore.QTimer(self)
            self._drain_timer.timeout.connect(self._drain_logs)
        self._drain_timer.start(100)

    def on_complete_missions(self):
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
        args = (self.log_queue, user_id, user_pwd, server)
        self.worker_process = Process(target=worker_complete_missions, args=args)
        self.worker_process.start()
        self.logger.info(f"미션 완료 프로세스 시작 (PID={self.worker_process.pid})")

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
