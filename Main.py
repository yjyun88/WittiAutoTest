# Main.py

import sys
import os
import subprocess, re
import logging
import shutil
from pathlib import Path

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QApplication, QMessageBox

from AutoTest import AutoTest_Start
from Main_Window import Ui_MainWindow
from multiprocessing import Process, Queue, freeze_support

# ─── API 요청 함수 임포트 ────────────────────────────────────────────────────────
from request_API import login_step1, login_step2, login_step2_for_all_children, get_curriculum_response, complete_today_missions

# ─── ADB 경로/실행 헬퍼 ─────────────────────────────────────────────────────────────
def get_adb_path():
    """
    exe로 빌드했을 때 포함된 adb.exe 경로를 반환.
    개발환경에서는 ./adb/adb.exe 를 사용.
    PyInstaller onefile 실행 시 내부 파일이 sys._MEIPASS로 풀립니다.
    """
    if hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS
    else:
        base = os.path.abspath(".")
    return os.path.join(base, "adb", "adb.exe")


def run_adb(args, **popen_kwargs):
    """
    번들된 ADB로 명령을 실행하여 결과를 반환합니다.
    기본적으로 check_output을 사용합니다.
    예: run_adb(["devices", "-l"], text=True)
    """
    adb = get_adb_path()
    return subprocess.check_output([adb] + args, **popen_kwargs)


def ensure_adb_server():
    """
    다른 adb와의 충돌을 피하기 위해, 번들된 adb로 서버를 재시작합니다.
    실패해도 앱 흐름을 막지 않습니다.
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


# ─── ADB 키 고정: ADB_VENDOR_KEYS 설정 & 최초 1회 키 생성 ───────────────────────
def ensure_adb_keys(app_name="AutoTest"):
    """
    1) ADB 키 저장 위치를 %LOCALAPPDATA%\\{app_name}\\.android 로 고정
    2) 사용자 기존 키(C:\\Users\\<User>\\.android\\adbkey*)가 있으면 복사(최초 1회)
    3) 없으면 번들 adb로 start-server 하여 키 생성
    4) 항상 동일 키를 쓰도록 ADB_VENDOR_KEYS 환경변수 설정
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


# ─── Worker 래퍼 함수 ───────────────────────────────────────────────────────────────
def worker_main(log_queue, btn_name, device_name, inputId, inputPwd, subjCd, itemCd, curtnSeq, title_name, server):
    import builtins, traceback
    def _print_via_queue(*args, sep=" ", end="\n", **kwargs):
        msg = sep.join(str(a) for a in args) + end
        log_queue.put(msg.rstrip("\n"))
    builtins.print = _print_via_queue

    try:
        print("워커 프로세스 시작")
        AutoTest_Start(btn_name, device_name, inputId, inputPwd, subjCd, itemCd, curtnSeq, title_name, server)
    except Exception as e:
        print(f"[ERROR] AutoTest_Start 중 예외: {e!r}")
        print(traceback.format_exc())

# ★ '오늘의 미션 완료'를 위한 새로운 Worker 함수
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

        # 1. 1차 로그인 -> 자녀 ID와 이름 목록을 모두 받음
        refreshToken, childIds, childNms = login_step1(user_id, user_pwd, server)
        if not refreshToken:
            print("[ERROR] 1차 로그인 실패. ID/PW나 서버 설정을 확인하세요.")
            return

        if not childIds:
            print("[INFO] 학습을 진행할 자녀 정보가 없습니다.")
            return

        # 2. 2차 로그인 (모든 자녀 토큰 발급)
        auth_tokens_by_child = login_step2_for_all_children(refreshToken, childIds, server)
        if not auth_tokens_by_child: # 딕셔너리가 비어있거나 None인 경우
            print("[ERROR] 2차 로그인 실패: 모든 자녀의 토큰을 발급받지 못했습니다.")
            return

        # 3. 모든 자녀의 미션을 취합할 리스트 준비
        all_child_missions = []

        # 4. 모든 자녀에 대해 커리큘럼 조회 (for loop)
        for child_id, child_name in zip(childIds, childNms):
            # 현재 자녀의 authToken 가져오기
            child_specific_auth_token = auth_tokens_by_child.get(child_id)
            if not child_specific_auth_token:
                print(f"[WARN] '{child_name}'({child_id})의 2차 로그인 토큰을 찾을 수 없습니다. 이 자녀의 미션을 건너뜁니다.")
                continue
            
            #print(f"\n> '{child_name}'({child_id})의 커리큘럼을 조회합니다...")
            response = get_curriculum_response(child_specific_auth_token, child_id, server)

            if response is None:
                print(f"[WARN] '{child_name}'의 커리큘럼 조회 실패. 다음 자녀로 넘어갑니다.")
                continue

            try:
                # API 응답에서 missionList 추출
                data = response.json()
                mission_list = data.get("result", {}).get("missionList", [])

                if not mission_list:
                    print(f"[INFO] '{child_name}'에게 할당된 오늘의 미션이 없습니다.")
                    continue

                # 각 미션에 자녀 이름과 ID를 추가해서 all_child_missions 리스트에 추가
                for mission in mission_list:
                    mission['childNm'] = child_name
                    mission['childId'] = child_id # 각 미션에 childId 추가
                    all_child_missions.append(mission)

            except Exception as e:
                print(f"[ERROR] '{child_name}'의 커리큘럼 응답 파싱 중 오류 발생: {e}")
                continue

        # 5. 취합된 모든 미션을 로그 출력 및 처리
        complete_today_missions(auth_tokens_by_child, all_child_missions, server) # 자녀별 토큰 딕셔너리 전달

        print("\n🎉 오늘의 미션 완료 처리가 성공적으로 종료되었습니다.")

    except Exception as e:
        print(f"[ERROR] 미션 완료 처리 중 예외 발생: {e!r}")
        print(traceback.format_exc())


if getattr(sys, "frozen", False):
    import __main__
    __main__.worker_main = worker_main
    __main__.worker_complete_missions = worker_complete_missions # ★ 새 워커 등록
    print("🔧 Registered workers on __main__")


# ─── GUI 메인 애플리케이션 ─────────────────────────────────────────────────────────
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

        self.ui.comboBox.setItemData(1, 1, QtCore.Qt.UserRole)
        self.ui.comboBox.setItemData(2, 2, QtCore.Qt.UserRole)
        self.ui.comboBox.setItemData(3, 3, QtCore.Qt.UserRole)
        self.ui.lineEdit.setText("MGguest011")
        self.ui.lineEdit_2.setText("mini1122@@")

        self.ui.pushButton.clicked.connect(self.close)
        self.ui.pushButton_2.clicked.connect(self.on_start)
        self.ui.pushButton_3.clicked.connect(self.on_start)
        self.ui.pushButton_4.clicked.connect(self.on_stop)
        self.ui.pushButton_5.clicked.connect(self.open_report_folder)
        self.ui.pushButton_6.clicked.connect(self.load_devices)
        self.ui.pushButton_7.clicked.connect(self.on_start)
        self.ui.pushButton_8.clicked.connect(self.clear_log)
        self.ui.pushButton_9.clicked.connect(self.on_complete_missions) # ★ 버튼 연결

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

        self.log_queue = Queue()
        args = (self.log_queue, btn_name, device_name, inputId, inputPwd, subjCd, itemCd, curtnSeq, title_name, server)
        self.worker_process = Process(target=worker_main, args=args)
        self.worker_process.start()
        self.logger.info(f"AutoTest 프로세스 시작 (PID={self.worker_process.pid})")

        if self._drain_timer is None:
            self._drain_timer = QtCore.QTimer(self)
            self._drain_timer.timeout.connect(self._drain_logs)
        self._drain_timer.start(100)

    # ★ '오늘의 미션 완료' 버튼을 위한 새 메서드
    def on_complete_missions(self):
        if self.worker_process and self.worker_process.is_alive():
            self.logger.warning("작업이 이미 실행 중입니다.")
            return

        user_id = self.ui.lineEdit.text().strip()
        user_pwd = self.ui.lineEdit_2.text().strip()
        server = self.ui.comboBox_6.currentText()

        if not all([user_id, user_pwd, server]):
            # 간단한 팝업 메시지로 사용자에게 알림
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
