# Main.py

import sys
import os
import subprocess, re
import logging
import shutil                               # ★ 추가
from pathlib import Path                    # ★ 추가

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QApplication

from AutoTest import AutoTest_Start
from Main_Window import Ui_MainWindow
from multiprocessing import Process, Queue, freeze_support


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
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # ★ 조용히
    except Exception:
        pass
    try:
        subprocess.check_output([get_adb_path(), "start-server"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # ★ 조용히
    except Exception:
        pass


# ─── ★ ADB 키 고정: ADB_VENDOR_KEYS 설정 & 최초 1회 키 생성 ───────────────────────
def ensure_adb_keys(app_name="AutoTest"):
    """
    1) ADB 키 저장 위치를 %LOCALAPPDATA%\\{app_name}\\.android 로 고정
    2) 사용자 기존 키(C:\\Users\\<User>\\.android\\adbkey*)가 있으면 복사(최초 1회)
    3) 없으면 번들 adb로 start-server 하여 키 생성
    4) 항상 동일 키를 쓰도록 ADB_VENDOR_KEYS 환경변수 설정
    """
    # 사용자 기본 위치의 기존 키
    user_home = Path(os.path.expandvars(r"%USERPROFILE%"))
    user_dot_android = user_home / ".android"
    user_key = user_dot_android / "adbkey"
    user_key_pub = user_dot_android / "adbkey.pub"

    # 안정적으로 우리가 쓸 고정 위치
    stable_root = Path(os.path.expandvars(r"%LOCALAPPDATA%")) / app_name / ".android"
    stable_root.mkdir(parents=True, exist_ok=True)
    stable_key = stable_root / "adbkey"
    stable_key_pub = stable_root / "adbkey.pub"

    # 기존 키가 있고, 안정 위치에 아직 없으면 복사
    if user_key.exists() and not stable_key.exists():
        try:
            shutil.copy2(user_key, stable_key)
            if user_key_pub.exists():
                shutil.copy2(user_key_pub, stable_key_pub)
        except Exception:
            # 복사 실패 시 이후 생성 단계로
            pass

    # ADB가 이 디렉토리의 키를 쓰도록 고정
    os.environ["ADB_VENDOR_KEYS"] = str(stable_root)

    # 키가 아직 없으면 adb가 자동 생성하게 1회 start-server
    if not stable_key.exists():
        adb = get_adb_path()
        try:
            subprocess.run([adb, "start-server"], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


# ★ 앱 시작 전에 ADB 키 고정(가장 먼저 실행되어야 함)
ensure_adb_keys(app_name="AutoTest")


# ─── Worker 래퍼 함수 ───────────────────────────────────────────────────────────────
def worker_main(log_queue, btn_name, device_name, inputId, inputPwd, subjCd, itemCd, curtnSeq, title_name, server):
    import builtins, traceback

    # print 몽키패치: sep, end 키워드 지원
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


if getattr(sys, "frozen", False):
    # multiprocessing spawn 환경에서 target을 재등록
    import __main__
    __main__.worker_main = worker_main
    print("🔧 Registered worker_main on __main__:", hasattr(__main__, "worker_main"))


# ─── GUI 메인 애플리케이션 ─────────────────────────────────────────────────────────
class MainApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.log_queue: Queue = None
        self.worker_process: Process = None
        self._drain_timer: QtCore.QTimer = None

        # 1) 표준 출력 리디렉션
        class EmittingStream(QtCore.QObject):
            textWritten = QtCore.pyqtSignal(str)
            def write(self, text):
                if not text or text == "\n":
                    return
                self.textWritten.emit(text)
            def flush(self):
                pass

        self.stdout_stream = EmittingStream()
        sys.stdout = self.stdout_stream
        sys.stderr = self.stdout_stream
        self.stdout_stream.textWritten.connect(self.append_log)

        # 2) 로깅 설정
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        self.logger = logging.getLogger(__name__)

        # 3) UI 세팅
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)

        # (선택) 번들된 ADB 서버 우선 사용을 위해 재시작
        ensure_adb_server()

        # 4) 디바이스 리스트 로드
        self.load_devices()

        # 5) userData 세팅
        self.ui.comboBox.setItemData(1, 1, QtCore.Qt.UserRole)
        self.ui.comboBox.setItemData(2, 2, QtCore.Qt.UserRole)
        self.ui.comboBox.setItemData(3, 3, QtCore.Qt.UserRole)
        self.ui.lineEdit.setText("MGguest011")
        self.ui.lineEdit_2.setText("mini1122@@")

        # 6) 버튼 연결
        self.ui.pushButton.clicked.connect(self.close)
        self.ui.pushButton_2.clicked.connect(self.on_start)
        self.ui.pushButton_3.clicked.connect(self.on_start)
        self.ui.pushButton_4.clicked.connect(self.on_stop)
        self.ui.pushButton_5.clicked.connect(self.open_report_folder)
        self.ui.pushButton_6.clicked.connect(self.load_devices)
        self.ui.pushButton_7.clicked.connect(self.on_start)
        self.ui.pushButton_8.clicked.connect(self.clear_log)

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
        """로그 창(PlainTextEdit)을 완전히 비웁니다."""
        self.ui.plainTextEdit.clear()

    @QtCore.pyqtSlot(str)
    def append_log(self, text):
        edit = self.ui.plainTextEdit
        edit.appendPlainText(text.rstrip("\n"))
        edit.verticalScrollBar().setValue(edit.verticalScrollBar().maximum())

    def load_devices(self):
        try:
            # ▶ 번들 ADB 사용
            out = run_adb(["devices", "-l"], text=True, encoding="utf-8", errors="ignore", timeout=20)
            lines = [ln for ln in out.strip().splitlines()[1:] if ln.strip()]

            entries = []
            for ln in lines:
                parts = ln.split()
                # 상태가 'device' 인 것만 (offline/unauthorized 등 제외)
                if len(parts) < 2 or parts[1] != "device":
                    continue

                dev_id = parts[0]  # USB 시리얼 / mDNS / ip:port
                model = next((p.split(":", 1)[1] for p in parts if p.startswith("model:")), "")
                model = model.replace("_", "-") if model else ""

                # Wi-Fi 판단 + mDNS에서 시리얼 힌트
                wifi = False
                serial_hint = ""
                # 예: adb-R9TX202G5NK-xxxx._adb-tls-connect._tcp
                m = re.search(r"^adb-([A-Za-z0-9]+)-", dev_id)
                if m and "._adb-tls-connect._tcp" in dev_id:
                    serial_hint = m.group(1)
                    wifi = True
                elif ":" in dev_id and dev_id.rsplit(":", 1)[1].isdigit():
                    wifi = True  # 192.168.x.x:port

                # 정규화 시리얼(canon): 1) mDNS 힌트 > 2) get-serialno > 3) dev_id
                if serial_hint:
                    canon = serial_hint
                else:
                    try:
                        canon = run_adb(["-s", dev_id, "get-serialno"], text=True, timeout=3).strip()
                    except Exception:
                        canon = dev_id

                entries.append({
                    "dev_id": dev_id,   # -s에 그대로 넣을 값 (wifi일 때 mDNS/IP)
                    "model": model,
                    "wifi": wifi,
                    "canon": canon      # 표준화된 시리얼(USB일 때 -s에 사용)
                })

            # 같은 시리얼(USB/Wi-Fi) 모두 보관
            by_serial = {}
            for e in entries:
                k = e["canon"]
                by_serial.setdefault(k, {})
                by_serial[k]['wifi' if e['wifi'] else 'usb'] = e

            # 라벨/데이터 구성: USB 먼저, 그 다음 Wi-Fi
            items = []
            for k, d in by_serial.items():
                if 'usb' in d:
                    e = d['usb']
                    label = f"{k} [USB]"
                    effective_id = e['canon']     # USB는 시리얼을 -s에 사용
                    items.append((label, effective_id))
                if 'wifi' in d:
                    e = d['wifi']
                    label = f"{k} [Wi-Fi]"
                    effective_id = e['dev_id']    # Wi-Fi는 mDNS/IP:port를 -s에 사용
                    items.append((label, effective_id))

            if not items:
                items = [("(no devices)", "")]

        except Exception as e:
            items = [(f"Error: {e}", "")]

        # 콤보 업데이트
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
        if btn_name == "pushButton_3" and (
            self.ui.comboBox.currentIndex()==0 or
            self.ui.comboBox_2.currentIndex()==0 or
            self.ui.comboBox_3.currentIndex()==0
        ):
            self.logger.error("과목, STEP, 호를 모두 선택해주세요.")
            return
        if btn_name == "pushButton_7" and self.ui.comboBox_5.currentIndex()==0:
            self.logger.error("Song을 선택해주세요.")
            return

        self.log_queue = Queue()
        args = (self.log_queue, btn_name, device_name, inputId, inputPwd, subjCd, itemCd, curtnSeq, title_name, server)
        self.worker_process = Process(target=worker_main, args=args)
        self.worker_process.start()
        self.logger.debug(f"process alive? {self.worker_process.is_alive()}")
        self.logger.info(f"AutoTest 프로세스 시작 (PID={self.worker_process.pid})")

        if self._drain_timer is None:
            self._drain_timer = QtCore.QTimer(self)
            self._drain_timer.timeout.connect(self._drain_logs)
        self._drain_timer.start(100)

    def _drain_logs(self):
        if not self.log_queue:
            return
        while not self.log_queue.empty():
            try:
                line = self.log_queue.get_nowait()
            except Exception:
                break
            self.append_log(line)

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
