# adb_recovery.py
"""
adb 연결 끊김 감지 / 재연결.

adb 서버는 실행 중인 모든 인스턴스가 공유하는 자원이라, 외부 요인(서버 재시작,
USB 재인증, 다른 툴의 개입)으로 언제든 끊길 수 있다. 끊기면 airtest의 screencap은
AdbError(stdout=b'', stderr=b'')로, minitouch는 ConnectionResetError로 터진다.

문제는 그 다음이다. 끊긴 상태에서 exists()가 던진 예외를 "화면을 못 찾았다"로
오해하면 복구 로직이 엉뚱한 판단을 내리고 이후 항목이 줄줄이 무너진다.
그래서 실패를 만나면 화면을 보기 전에 '연결이 살아있는지'부터 확인한다.
"""
import time

from airtest.core.api import connect_device
from airtest.core.error import AdbError, DeviceConnectionError
from airtest.core.helper import G

# connect_device에 쓴 URI. 재연결 시 동일 옵션(cap_method 등)으로 다시 붙어야 한다.
_DEVICE_URI = None

# 재연결 대기 기본값. USB 재인증/서버 재시작은 보통 10초 안에 끝나지만,
# 기기가 화면 잠금 상태로 늦게 올라오는 경우가 있어 여유를 둔다.
RECONNECT_TIMEOUT = 90
RECONNECT_INTERVAL = 5


def set_device_uri(uri):
    """connect_device 직후 호출. 재연결에 쓸 URI를 기억한다."""
    global _DEVICE_URI
    _DEVICE_URI = uri


def is_disconnect_error(exc):
    """
    예외가 'adb 연결이 끊겼다'를 뜻하는지 판별한다.

    끊김과 단순 실패를 구분하지 못하면 멀쩡한 실패에도 재연결을 돌려
    시간만 버리게 되므로, 끊김 특유의 신호만 본다.
    """
    if isinstance(exc, (ConnectionResetError, ConnectionAbortedError,
                        BrokenPipeError, DeviceConnectionError)):
        return True
    if isinstance(exc, AdbError):
        # 기기가 사라진 상태의 screencap은 stdout/stderr가 모두 비어서 돌아온다.
        blob = f"{exc.stdout!r} {exc.stderr!r}".lower()
        if exc.stdout in (b"", "", None) and exc.stderr in (b"", "", None):
            return True
        return any(k in blob for k in (
            "device offline", "device not found", "no devices",
            "closed", "protocol fault", "connection reset",
        ))
    return False


def device_alive():
    """현재 기기가 adb에서 'device' 상태로 보이는지."""
    dev = G.DEVICE
    if dev is None:
        return False
    try:
        return dev.adb.get_status() == "device"
    except Exception:
        return False


def reconnect_device(timeout=RECONNECT_TIMEOUT, interval=RECONNECT_INTERVAL):
    """
    기기가 다시 붙을 때까지 재연결을 시도한다.

    connect_device는 같은 uuid의 기존 인스턴스를 교체하므로(G.add_device),
    죽은 인스턴스가 목록에 쌓이지 않는다. 다만 이전 인스턴스가 물고 있던
    minitouch/minicap 소켓은 남으므로 먼저 정리한다.
    """
    if not _DEVICE_URI:
        print("[Recover] 연결 URI를 모릅니다 (set_device_uri 미호출) → 재연결 불가")
        return False

    old = G.DEVICE
    if old is not None:
        try:
            old.disconnect()
        except Exception as e:
            print(f"[Recover] 이전 연결 정리 중 무시된 오류: {e}")

    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            connect_device(_DEVICE_URI)
            if device_alive():
                print(f"[Recover] 기기 재연결 성공 (시도 {attempt}회)")
                return True
            print(f"[Recover] 재연결했으나 아직 device 상태가 아님 (시도 {attempt})")
        except Exception as e:
            print(f"[Recover] 재연결 시도 {attempt} 실패: {type(e).__name__}: {e}")
        time.sleep(interval)

    print(f"[Recover] {timeout}s 내에 기기를 되찾지 못했습니다")
    return False


def ensure_device_alive(timeout=RECONNECT_TIMEOUT):
    """
    연결이 살아있으면 True, 끊겼으면 재연결까지 시도한 결과를 반환한다.
    화면 판정(exists/touch) 앞에 두어, 끊긴 화면을 읽고 오판하는 것을 막는다.
    """
    if device_alive():
        return True
    print("[Recover] adb 연결이 끊긴 것으로 보입니다 → 재연결 시도")
    return reconnect_device(timeout=timeout)


def recover_if_disconnected(exc, timeout=RECONNECT_TIMEOUT):
    """
    예외가 끊김이면 재연결하고 그 결과를 반환한다.
    끊김이 아니면 None을 반환해 '복구 대상이 아님'을 구분한다.
    """
    if not is_disconnect_error(exc):
        return None
    print(f"[Recover] 연결 끊김 감지: {type(exc).__name__}: {exc}")
    return reconnect_device(timeout=timeout)
