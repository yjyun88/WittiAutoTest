import requests
import base64
import json

# from sympy.strategies.core import switch # 사용하지 않으므로 제거

# 통합 로그인 API
def login_step1(inputId, inputPwd, server):
    """
    1차 로그인: refreshToken과 childIds 리스트를 반환
    """
    try:
        # Base64 인코딩
        encodedId = base64.b64encode(inputId.encode("utf-8")).decode("utf-8")
        encodedPwd = base64.b64encode(inputPwd.encode("utf-8")).decode("utf-8")

        login_url = f"https://{server}.wittiverse.com/v2/authenticate/login"
        login_params = {"loginTp": "L", "ptnrId": "1102"}
        login_headers = {
            "Content-Type": "application/json",
            "X-device-info": "QW5kcm9pZC4zMzo6OlI5VFgyMDJHNUFFTTo6OlI5VFgyMDJHNUFFTTo6OktOT1g6OjpTTS1YMjE2Ojo6YXBwLjE0Ojo6"
        }
        login_body = {"loginId": encodedId, "loginPwd": encodedPwd}

        print(f"1차 로그인 요청 (ID: {inputId})")
        resp = requests.post(login_url,
                             headers=login_headers,
                             params=login_params,
                             json=login_body,
                             timeout=20)
        resp.raise_for_status()  # 200번대 응답 코드가 아니면 예외를 발생시킴

        data = resp.json()
        refreshToken = data.get("result", {}).get("refreshToken")
        childList = data.get("result", {}).get("childList", [])
        childIds = sorted([c["childId"] for c in childList])
        childNms = sorted([c["childNm"] for c in childList])

        print("1차 로그인 성공")
        return refreshToken, childIds, childNms

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 1차 로그인 실패 (네트워크/서버 오류): {e}")
        return None, [], []
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[ERROR] 1차 로그인 응답 데이터 파싱 실패: {e}")
        return None, [], []
    except Exception as e:
        print(f"[ERROR] 1차 로그인 중 예기치 않은 오류 발생: {e}")
        return None, [], []


# 이슈 토큰 발급 API
def login_step2(refreshToken, childIds, server):
    """
    2차 로그인(토큰발급): authToken 을 반환
    """
    try:
        if not childIds:
            print("[ERROR] 2차 로그인 실패: 대상 자녀 ID 목록이 비어있습니다.")
            return None
            
        childId = childIds[1] if len(childIds) > 1 else childIds[0]
        url = f"https://{server}.wittiverse.com/v2/authenticate/token/issue"
        params = {"childId": childId}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {refreshToken}",
            "X-device-info": "QW5kcm9pZC4zMzo6OlI5VFgyMDJHNUFFTTo6OlI5VFgyMDJHNUFFTTo6OktOT1g6OjpTTS1YMjE2Ojo6YXBwLjE0Ojo6"
        }
        
        print(f"2차 로그인 요청 (childId: {childId})")
        resp = requests.get(url, headers=headers, params=params, timeout=20)
        resp.raise_for_status()

        data = resp.json()
        authToken = data.get("result", {}).get("authToken")

        print("2차 로그인 성공")
        return authToken

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 2차 로그인 실패 (네트워크/서버 오류): {e}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[ERROR] 2차 로그인 응답 데이터 파싱 실패: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 2차 로그인 중 예기치 않은 오류 발생: {e}")
        return None


# 런처 커리큘럼 호출 API
def get_curriculum_response(authToken, childId, server):
    try:
        url = f"https://{server}.wittiverse.com/v2/witti-box/curriculum?childId={childId}"
        headers = {
            'Authorization': f'Bearer {authToken}'
        }
        
        print(f"런처 커리큘럼 조회 (childId: {childId})")
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        print("런처 커리큘럼 조회 성공")
        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 런처 커리큘럼 조회 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 런처 커리큘럼 조회 중 예기치 않은 오류 발생: {e}")
        return None


# 위티스쿨 > 아람북월드 커리큘럼 호출 API
def get_school_aram_content(authToken, subjCd, itemCd, curtnSeq, server):
    try:
        itemCd_str = ""
        if itemCd == 1:
            itemCd_str = "AR0000010"
        elif itemCd == 2:
            itemCd_str = "AR0000011"

        subjCd_str = ""
        if subjCd == 1:
            subjCd_str = "KOR"
        elif subjCd == 2:
            subjCd_str = "MTH"
        elif subjCd == 3:
            subjCd_str = "SCI"

        url = f"https://{server}.wittiverse.com/v2/witti-school/aram-bookworld/subject/{subjCd_str}"
        params = {
            "ptnrId" : "1102",
            "prodId" : "PI-00000000000000001",
            "itemCd" : itemCd_str,
            "curtnSeq" : curtnSeq
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {authToken}",
            "X-device-info": "QW5kcm9pZC4zMzo6OlI5VFgyMDJHNUFFTTo6OlI5VFgyMDJHNUFFTTo6OktOT1g6OjpTTS1YMjE2Ojo6YXBwLjE0Ojo6"
        }
        
        print(f"위티스쿨 커리큘럼 조회 (subjCd: {subjCd_str}, itemCd: {itemCd_str})")
        resp = requests.get(url, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        
        data = resp.json()
        book_name = next(
            (
            book.get("bookNm")
            for curtn in data.get("result", {}).get("curtnList", [])
            for book  in curtn.get("bookList", [])
            ),
            None
        )

        items = []
        for curtn in data.get("result", {}).get("curtnList", []):
            for category in curtn.get("actCatgryList", []):
                for cont in category.get("contsList", []):
                    tag = cont.get("actTag")
                    url = cont.get("contsThumbUrl")
                    if tag and url:
                        items.append({"actTag": tag, "contsThumbUrl": url})

        subjCd_kor = ""
        if subjCd_str == "KOR":
            subjCd_kor = "한글"
        elif subjCd_str == "MTH":
            subjCd_kor = "수학"
        elif subjCd_str == "SCI":
            subjCd_kor = "창의"

        print("위티스쿨 커리큘럼 조회 성공")
        return book_name, subjCd_kor, items

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 위티스쿨 커리큘럼 조회 실패 (네트워크/서버 오류): {e}")
        return None, "", []
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[ERROR] 위티스쿨 커리큘럼 응답 데이터 파싱 실패: {e}")
        return None, "", []
    except Exception as e:
        print(f"[ERROR] 위티스쿨 커리큘럼 조회 중 예기치 않은 오류 발생: {e}")
        return None, "", []