import builtins
import inspect

# 원래 print 함수 백업
_orig_print = builtins.print


# 터미널 Log의 print() 함수 출력 텍스트 색상 변경
def print(*args, color="\033[92m", **kwargs):
    """
    - 기본 컬러: ANSI 92 (밝은 초록)
    - logging 모듈 내부 호출은 컬러 적용 안 함
    """
    # 호출 모듈 이름 가져오기
    caller = inspect.currentframe().f_back.f_globals.get("__name__", "")
    if caller.startswith("logging"):
        # logging.debug 등에서 온 호출은 일반 print
        return _orig_print(*args, **kwargs)

    # 컬러 적용 출력
    text = " ".join(str(a) for a in args)
    return _orig_print(f"{color}{text}\033[0m", **kwargs)

# builtins.print 을 새 함수로 교체
builtins.print = print
