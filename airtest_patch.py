# airtest_patch.py
"""airtest 1.3.5의 ADB.push() 버그를 우회한다.

airtest/core/android/adb.py 의 push()는 확장자 유무로 파일/디렉터리를 판별한다.
minicap/minitouch 처럼 확장자가 없는 바이너리를 확장자 없는 경로로 push 하면
목적지를 디렉터리로 오인해서 아래 순서로 스스로 결과물을 지운다.

    dst_parent = "/data/local/tmp/minicap"          # 파일 자리를 부모 디렉터리로 오인
    mkdir -p /data/local/tmp/minicap                # 파일이 와야 할 자리에 디렉터리 생성
    tmp_path   = "/data/local/tmp/minicap"          # TMP_PATH + basename → remote 와 동일
    push  → /data/local/tmp/minicap/minicap         # 디렉터리 안으로 들어감
    cp -frp ".../minicap/*" ".../minicap"           # 자기 자신 복사 → 실패
    mv ".../minicap" ".../minicap"                  # → mv: bad ...: Invalid argument
    finally: rm -r "/data/local/tmp/minicap"        # 방금 올린 바이너리를 통째로 삭제

그 결과 minicap 배포가 매번 실패하고, airtest 는 JAVACAP 으로 폴백하면서
Yosemite.apk(com.netease.nie.yosemite)를 기기에 설치한다. 이 APK 가
구글 플레이 프로텍트에 유해 앱으로 잡힌다.

여기서는 문제가 되는 install() 두 개만 raw `adb push` 를 쓰도록 교체한다.
확장자가 있는 minicap.so / *.jar 는 원래 경로로도 정상이라 건드리지 않는다.

두 번째로 Yosemite.apk 를 airtest 1.4.3 이 배포하는 449 로 교체한다.
Android 16(SDK 36) 기기는 minicap 이 아예 불가능하다. 네이티브 ABI 가 바뀌어
airtest 가 동봉한 minicap.so 는 android-34/35 모두 링크에 실패한다.

    CANNOT LINK EXECUTABLE: cannot locate symbol
    "_ZTVN7android21SurfaceComposerClient11TransactionE"

이 기기에서 남는 선택지는 JAVACAP 과 ADBCAP 뿐인데, 실측하면 차이가 크다.
(SM-X216N / Android 16 기준, 프레임당)

    JAVACAP + Yosemite 449   340 ms
    ADBCAP                  2977 ms      ← screencap 자체가 느리다. USB 로 바꿔도 같다.

airtest 1.3.5 가 동봉한 Yosemite 430 으로는 JAVACAP 이 실패하고, 449 로 올리면
동작한다. airtest 본체는 1.3.5 로 두고 APK 만 vendor/ 에 둔 449 로 바꾼다.

세 번째로 JAVACAP 의 화면 회전을 보정한다.
Minicap 은 `-P 1200x1920@1200x1920/90` 처럼 회전 각도를 기기에 넘겨 이미 돌아간
프레임을 받고, AdbCap 도 나름의 처리가 있다. 그런데 Javacap 에는 회전 처리가
아예 없다. 생성자가 rotation_watcher 를 받고도 쓰지 않고, 받은 프레임을 그대로
돌려준다. 그래서 가로 화면 기기에서 세로(1200x1920) 이미지가 나온다.

세로로 누운 스크린샷은 해상도만 어긋나는 게 아니라 ROI 가 통째로 틀어진다.
예를 들어 우상단 ROI 를 보는 class_select() 의 setup_menu 탐색은, 실제로는
좌상단에 있는 설정 버튼을 영영 찾지 못한다. AOS13 기기는 MINICAP 을 타서
멀쩡하고 AOS16 기기만 실패하는 이유가 이것이다.

방향은 실측으로 정했다. 같은 순간의 화면을 두 방식으로 찍어 비교하면

    javacap 을 시계방향 90도 회전 -> adbcap 과 mean_absdiff  2.25   (애니메이션 차이)
    반시계 90도 회전             -> adbcap 과 mean_absdiff 46.35
"""
import os
import sys

from airtest.core.android.constant import STFLIB
from airtest.utils.logger import get_logger

LOGGING = get_logger(__name__)

_PATCHED = False


def _raw_push(adb, local, remote):
    """중간 경유 없이 곧바로 목적지로 push 한다.

    이전 실행이 남긴 동명의 디렉터리가 있으면 push 가 그 안으로 들어가므로 먼저 지운다.
    """
    try:
        adb.shell('rm -rf "%s"' % remote)
    except Exception:
        pass
    adb.cmd(["push", local, remote])


def _resolve_minicap_so(sdk, rel, abi):
    """기기에 맞는 minicap.so 경로를 고른다.

    airtest 1.3.5가 동봉한 라이브러리는 android-34까지다. 그보다 높은 SDK 기기는
    정확히 맞는 파일이 없으므로 사용 가능한 가장 높은 버전으로 내려서 시도한다.
    (Android 16처럼 네이티브 ABI가 바뀐 기기에서는 이래도 링크에 실패하는데,
    그때는 airtest가 알아서 다음 캡처 방식으로 폴백한다.)
    """
    pattern = os.path.join(STFLIB, "minicap-shared/aosp/libs/android-%s/%s/minicap.so")

    for key in (sdk, rel):
        path = pattern % (key, abi)
        if os.path.isfile(path):
            return path

    libs_dir = os.path.join(STFLIB, "minicap-shared", "aosp", "libs")
    available = []
    try:
        for name in os.listdir(libs_dir):
            if not name.startswith("android-"):
                continue
            suffix = name[len("android-"):]
            if not suffix.isdigit():
                continue
            if os.path.isfile(os.path.join(libs_dir, name, abi, "minicap.so")):
                available.append(int(suffix))
    except OSError:
        pass

    if available:
        best = max(available)
        LOGGING.warning(
            "no minicap.so for sdk %s, falling back to android-%s", sdk, best)
        return pattern % (best, abi)

    return pattern % (sdk, abi)


def _minicap_install(self):
    """airtest.core.android.cap_methods.minicap.Minicap.install 대체."""
    abi = self.adb.getprop("ro.product.cpu.abi")
    pre = self.adb.getprop("ro.build.version.preview_sdk")
    rel = self.adb.getprop("ro.build.version.release")
    sdk = self.adb.sdk_version

    if pre.isdigit() and int(pre) > 0:
        sdk += 1

    binfile = "minicap" if sdk >= 16 else "minicap-nopie"
    device_dir = "/data/local/tmp"

    path = os.path.join(STFLIB, abi, binfile)
    _raw_push(self.adb, path, "%s/minicap" % device_dir)
    self.adb.shell("chmod 755 %s/minicap" % device_dir)

    path = _resolve_minicap_so(sdk, rel, abi)

    _raw_push(self.adb, path, "%s/minicap.so" % device_dir)
    self.adb.shell("chmod 755 %s/minicap.so" % device_dir)
    LOGGING.info("minicap installation finished (patched)")


def _minitouch_install(self):
    """airtest.core.android.touch_methods.minitouch.Minitouch.install 대체."""
    abi = self.adb.getprop("ro.product.cpu.abi")
    sdk = int(self.adb.getprop("ro.build.version.sdk"))

    binfile = "minitouch" if sdk >= 16 else "minitouch-nopie"

    device_dir = os.path.dirname(self.path_in_android)
    path = os.path.join(STFLIB, abi, binfile)

    try:
        exists_file = self.adb.file_size(self.path_in_android)
    except Exception:
        pass
    else:
        if exists_file and exists_file == int(os.path.getsize(path)):
            LOGGING.debug("install_minitouch skipped")
            return
        self.uninstall()

    _raw_push(self.adb, path, "%s/minitouch" % device_dir)
    self.adb.shell("chmod 755 %s/minitouch" % device_dir)
    LOGGING.info("install_minitouch finished (patched)")


def _bundled_yosemite_apk():
    """동봉한 Yosemite 449 경로. 개발 환경과 PyInstaller 빌드 모두에서 찾는다."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "vendor", "airtest_apks", "Yosemite.apk")
    return path if os.path.isfile(path) else None


def _patch_yosemite_apk():
    """airtest 가 설치할 Yosemite.apk 를 449 로 바꾼다.

    yosemite.py 는 `from .constant import YOSEMITE_APK` 로 이름을 이미 가져간 뒤라
    constant 만 고쳐서는 반영되지 않는다. 참조하는 모듈 쪽도 함께 덮는다.
    """
    apk = _bundled_yosemite_apk()
    if not apk:
        LOGGING.warning(
            "vendor/airtest_apks/Yosemite.apk 없음. airtest 기본 APK(430)를 쓴다. "
            "Android 16 기기에서는 JAVACAP이 실패한다.")
        return

    from airtest.core.android import constant, yosemite

    constant.YOSEMITE_APK = apk
    yosemite.YOSEMITE_APK = apk
    LOGGING.debug("Yosemite.apk overridden -> %s", apk)


def _javacap_rotation(cap):
    """현재 화면 회전 각도(0/90/180/270)."""
    watcher = getattr(cap, "_witti_rotation_watcher", None)
    if watcher is not None:
        ori = getattr(watcher, "current_orientation", None)
        if ori is not None:
            return int(ori) * 90

    # rotation_watcher가 아직 값을 못 받았으면 display_info로 대체한다.
    ori_function = getattr(cap, "_witti_ori_function", None)
    if ori_function is not None:
        try:
            return int(ori_function().get("orientation", 0)) * 90
        except Exception:
            pass
    return 0


def _patch_javacap_rotation():
    """Javacap 이 화면 회전을 반영하도록 생성자와 snapshot 을 교체한다."""
    from airtest import aircv
    from airtest.core.android.cap_methods.base_cap import BaseCap
    from airtest.core.android.cap_methods.javacap import Javacap

    original_init = Javacap.__init__

    def patched_init(self, adb, *args, **kwargs):
        original_init(self, adb, *args, **kwargs)
        # 원본은 이 두 인자를 받고도 쓰지 않는다. 회전 보정에 필요하므로 붙들어 둔다.
        self._witti_rotation_watcher = kwargs.get("rotation_watcher")
        self._witti_ori_function = kwargs.get("ori_function")

    def patched_snapshot(self, ensure_orientation=True, *args, **kwargs):
        screen = BaseCap.snapshot(self)
        if screen is None:
            return None
        if ensure_orientation:
            angle = _javacap_rotation(self)
            if angle:
                screen = aircv.rotate(screen, angle, clockwise=True)
        return screen

    Javacap.__init__ = patched_init
    Javacap.snapshot = patched_snapshot


def apply_patches():
    """airtest 를 쓰기 전에 한 번만 호출한다. 두 번 이상 불러도 안전하다."""
    global _PATCHED
    if _PATCHED:
        return

    from airtest.core.android.cap_methods.minicap import Minicap
    from airtest.core.android.touch_methods.minitouch import Minitouch

    Minicap.install = _minicap_install
    Minitouch.install = _minitouch_install
    _patch_yosemite_apk()
    _patch_javacap_rotation()

    _PATCHED = True
    LOGGING.debug("airtest patches applied")
