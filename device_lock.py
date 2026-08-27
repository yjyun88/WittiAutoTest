# device_lock.py
"""
기기 단위 중복 실행 방지.

여러 인스턴스를 동시에 돌릴 때 같은 기기를 두 번 테스트하면 조작이 뒤엉켜
양쪽 결과가 모두 무의미해진다. USB는 adb의 배타적 접근이 우연히 막아주지만,
무선(TCP) 연결은 여러 서버가 같은 기기에 각자 붙을 수 있어 adb 차원에서는
막을 방법이 없다. 그래서 앱이 직접 잠근다.

잠금은 '파일을 만들고 지우는' 방식이 아니라 OS 파일 잠금을 쓴다.
만들고 지우는 방식은 강제 종료·크래시 때 잠금 파일이 남아 그 기기를 다시는
쓸 수 없게 되지만, OS 잠금은 프로세스가 어떤 식으로 죽든 커널이 풀어준다.

잠금 파일은 인스턴스별 폴더가 아니라 %LOCALAPPDATA% 아래 고정 경로에 둔다.
서로 다른 폴더에서 실행된 인스턴스들이 같은 곳을 봐야 서로를 인식한다.
"""
import json
import os
import sys

try:
    import msvcrt
except ImportError:  # pragma: no cover - 이 앱은 Windows 전용
    msvcrt = None


APP_NAME = "AutoTest"


def lock_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    path = os.path.join(base, APP_NAME, "locks")
    os.makedirs(path, exist_ok=True)
    return path


def _safe_name(serial):
    """시리얼을 파일명으로 쓸 수 있게 정리한다 (무선 기기 이름에는 '.'와 '_'가 섞여 있다)."""
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(serial))[:120]


def _lock_path(serial):
    return os.path.join(lock_dir(), f"{_safe_name(serial)}.lock")


def _info_path(serial):
    return os.path.join(lock_dir(), f"{_safe_name(serial)}.info")


def _try_lock(fh):
    """비블로킹 배타 잠금. 성공하면 True, 이미 잠겨 있으면 False."""
    if msvcrt is None:
        return True
    try:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        return False


def _unlock(fh):
    if msvcrt is None:
        return
    try:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


def read_holder(serial):
    """
    잠금을 쥔 인스턴스 정보를 반환한다. 잠겨 있지 않으면 None.

    정보 파일(.info)은 참고용이라 낡은 값이 남아 있을 수 있다.
    '실제로 잠겨 있는지'는 항상 .lock 파일을 직접 시험해서 판단한다.
    """
    path = _lock_path(serial)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "a+b") as fh:
            if _try_lock(fh):
                # 잡혔다 = 아무도 안 쓰고 있다. 바로 놓아준다.
                _unlock(fh)
                return None
    except OSError:
        # 열지도 못하면 누군가 쓰는 중으로 본다 (정보는 알 수 없음)
        return {}

    try:
        with open(_info_path(serial), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def describe_holder(serial):
    """목록에 덧붙일 '사용 중' 문구. 잠겨 있지 않으면 빈 문자열."""
    holder = read_holder(serial)
    if holder is None:
        return ""
    pid = holder.get("pid")
    label = holder.get("instance")
    if pid and label:
        return f" - 사용 중 (PID {pid}, {label})"
    if pid:
        return f" - 사용 중 (PID {pid})"
    return " - 사용 중"


class DeviceLock:
    """
    한 기기에 대한 잠금. 획득에 성공하면 프로세스가 살아있는 동안 유지된다.

    핸들을 계속 쥐고 있는 것이 잠금 그 자체다. 닫거나 프로세스가 죽으면
    커널이 자동으로 풀어주므로 뒤처리를 놓칠 걱정이 없다.
    """

    def __init__(self):
        self.serial = None
        self._fh = None

    @property
    def held(self):
        return self._fh is not None

    def acquire(self, serial, instance="", device_label=""):
        """잠금을 얻으면 True. 이미 다른 인스턴스가 쓰고 있으면 False."""
        if self.held:
            if self.serial == serial:
                return True
            self.release()

        try:
            fh = open(_lock_path(serial), "a+b")
        except OSError:
            return False

        if not _try_lock(fh):
            fh.close()
            return False

        self._fh, self.serial = fh, serial
        # 누가 쓰는지 사람이 알아볼 수 있게 남긴다 (판정에는 쓰지 않는다)
        try:
            with open(_info_path(serial), "w", encoding="utf-8") as f:
                json.dump({
                    "pid": os.getpid(),
                    "instance": instance or os.path.basename(
                        os.path.dirname(sys.executable if getattr(sys, "frozen", False)
                                        else os.path.abspath(__file__))),
                    "device": device_label,
                }, f, ensure_ascii=False)
        except OSError:
            pass
        return True

    def release(self):
        if not self.held:
            return
        serial, fh = self.serial, self._fh
        self._fh, self.serial = None, None
        _unlock(fh)
        try:
            fh.close()
        except OSError:
            pass
        try:
            os.remove(_info_path(serial))
        except OSError:
            pass
