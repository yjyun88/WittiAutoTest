import requests
import base64
import json

STUDY_ACCESS_MEM_NM = None
STUDY_ACCESS_MEM_ID = None
STUDY_ACCESS_AUTH_TOKEN = None


# 통합 로그인 API
def login_step1(inputId, inputPwd, server):
    """
    1차 로그인: authToken 반환
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
        authToken = data.get("result", {}).get("authToken")
        print("1차 로그인 성공")
        return authToken

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 1차 로그인 실패 (네트워크/서버 오류): {e}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[ERROR] 1차 로그인 응답 데이터 파싱 실패: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 1차 로그인 중 예기치 않은 오류 발생: {e}")
        return None


def class_list(authToken, inputId, server):
    """
    클래스 목록 조회 API
    GET {server}/v2/authenticate/classes/{inputId}
    Authorization: Bearer {authToken}
    """
    try:
        url = f"https://{server}.wittiverse.com/v2/authenticate/classes/{inputId}"
        headers = {
            "Authorization": f"Bearer {authToken}"
        }

        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] class_list 조회 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] class_list 조회 중 예기치 않은 오류 발생: {e}")
        return None


def student_list_by_class(authToken, classId, server):
    """
    학생 목록 조회 API
    GET {server}/v2/authenticate/classes?classId={classId}
    Authorization: Bearer {authToken}
    """
    try:
        url = f"https://{server}.wittiverse.com/v2/authenticate/classes"
        params = {
            "classId": classId
        }
        headers = {
            "Authorization": f"Bearer {authToken}"
        }

        response = requests.get(url, params=params, headers=headers, timeout=20)
        response.raise_for_status()
        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] student_list 조회 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] student_list 조회 중 예기치 않은 오류 발생: {e}")
        return None


def authenticate_study_access(studentId, loginId, server):
    """
    학습 접근 인증 API
    POST {server}/v2/authenticate/study/access?loginTp=L&autoLoginYn=Y&ptnrId=1000
    Body: {studentId, loginId, accessType="C"}
    응답의 memId, authToken 을 전역 변수에 저장
    """
    global STUDY_ACCESS_MEM_NM, STUDY_ACCESS_MEM_ID, STUDY_ACCESS_AUTH_TOKEN

    try:
        url = f"https://{server}.wittiverse.com/v2/authenticate/study/access"
        params = {
            "loginTp": "L",
            "autoLoginYn": "Y",
            "ptnrId": "1000",
        }
        normalized_student_id = int(studentId) if str(studentId).isdigit() else studentId
        headers = {
            "Content-Type": "application/json",
            "X-device-info": "QW5kcm9pZC4zMzo6OlI5VFgyMDJHNUFFTTo6OlI5VFgyMDJHNUFFTTo6OktOT1g6OjpTTS1YMjE2Ojo6YXBwLjE0Ojo6",
        }
        body = {
            "studentId": normalized_student_id,
            "loginId": loginId,
            "accessType": "C",
        }

        response = requests.post(
            url,
            params=params,
            headers=headers,
            json=body,
            timeout=20,
        )
        response.raise_for_status()

        data = response.json()
        result = data.get("result", {})
        STUDY_ACCESS_MEM_NM = result.get("memNm")
        STUDY_ACCESS_MEM_ID = result.get("memId")
        STUDY_ACCESS_AUTH_TOKEN = result.get("authToken")

        return response

    except requests.exceptions.HTTPError as e:
        status = "-"
        resp_text = ""
        try:
            status = e.response.status_code if e.response is not None else "-"
            resp_text = e.response.text if e.response is not None else ""
        except Exception:
            pass
        print(
            f"[ERROR] study/access 인증 실패 (HTTP {status}): "
            f"studentId={studentId}, loginId={loginId}, body={resp_text}"
        )
        return None
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] study/access 인증 실패 (네트워크/서버 오류): {e}")
        return None
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[ERROR] study/access 응답 데이터 파싱 실패: {e}")
        return None
    except Exception as e:
        print(f"[ERROR] study/access 인증 중 예기치 않은 오류 발생: {e}")
        return None


def authenticate_study_access_detailed(studentId, loginId, server):
    """
    study/access 호출 상세 결과 반환 (HTTP 에러 포함)
    return dict:
      {
        "ok": bool,
        "status_code": int|None,
        "data": dict|None,
        "error": str|None
      }
    """
    global STUDY_ACCESS_MEM_NM, STUDY_ACCESS_MEM_ID, STUDY_ACCESS_AUTH_TOKEN

    try:
        url = f"https://{server}.wittiverse.com/v2/authenticate/study/access"
        params = {
            "loginTp": "L",
            "autoLoginYn": "Y",
            "ptnrId": "1000",
        }
        normalized_student_id = int(studentId) if str(studentId).isdigit() else studentId
        headers = {
            "Content-Type": "application/json",
            "X-device-info": "QW5kcm9pZC4zMzo6OlI5VFgyMDJHNUFFTTo6OlI5VFgyMDJHNUFFTTo6OktOT1g6OjpTTS1YMjE2Ojo6YXBwLjE0Ojo6",
        }
        body = {
            "studentId": normalized_student_id,
            "loginId": loginId,
            "accessType": "C",
        }

        response = requests.post(
            url,
            params=params,
            headers=headers,
            json=body,
            timeout=20,
        )

        status_code = response.status_code
        data = None
        try:
            data = response.json()
        except Exception:
            data = None

        if response.ok:
            result = (data or {}).get("result", {})
            STUDY_ACCESS_MEM_NM = result.get("memNm")
            STUDY_ACCESS_MEM_ID = result.get("memId")
            STUDY_ACCESS_AUTH_TOKEN = result.get("authToken")
            return {
                "ok": True,
                "status_code": status_code,
                "data": data,
                "error": None,
            }

        return {
            "ok": False,
            "status_code": status_code,
            "data": data,
            "error": response.text,
        }

    except requests.exceptions.RequestException as e:
        return {
            "ok": False,
            "status_code": None,
            "data": None,
            "error": str(e),
        }
    except Exception as e:
        return {
            "ok": False,
            "status_code": None,
            "data": None,
            "error": str(e),
        }


def get_study_access_auth():
    """
    최신 study/access 결과 전역값 조회
    """
    return STUDY_ACCESS_MEM_NM, STUDY_ACCESS_MEM_ID, STUDY_ACCESS_AUTH_TOKEN


# 런처 커리큘럼 호출 API
def get_curriculum_response(authToken, childId, server):
    try:
        url = f"https://{server}.wittiverse.com/v2/witti-box/curriculum?childId={childId}"
        headers = {
            'Authorization': f'Bearer {authToken}'
        }
        
        #print(f"런처 커리큘럼 조회 (childId: {childId})")
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        #print("런처 커리큘럼 조회 성공")
        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 런처 커리큘럼 조회 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 런처 커리큘럼 조회 중 예기치 않은 오류 발생: {e}")
        return None


# 오늘의 미션 '로그 출력' 및 '학습 완료 처리'
def complete_today_missions(auth_tokens_by_child, all_child_missions, server):
    """
    모든 자녀의 미션 목록을 먼저 로그로 출력한 뒤,
    comTypeNm에 따라 각기 다른 완료 API를 호출하여 처리합니다.
    """
    # --- 1단계: 모든 미션 목록 로그 출력 ---
    if not all_child_missions:
        print("[INFO] 확인된 오늘의 미션이 없습니다.")
        return

    print(f"--- 모든 자녀의 미션 목록 (총 {len(all_child_missions)}개) ---")
    
    current_child_info = "" # childId 와 childNm 을 함께 관리하기 위함
    for mission in all_child_missions:
        child_id_from_mission = mission.get("childId", "알 수 없는 자녀 ID") # Main.py에서 추가한 childId
        child_name_from_mission = mission.get("childNm", "알 수 없는 자녀명")

        # 자녀 정보가 바뀔 때만 출력
        if current_child_info != f"{child_id_from_mission} ({child_name_from_mission})":
            current_child_info = f"{child_id_from_mission} ({child_name_from_mission})"
            print(f"[ 자녀: {child_name_from_mission} (ID: {child_id_from_mission}) ]")
        
        mission_details = (
            f"  - 이름: {mission.get('name', 'N/A')}"
            f"    (타입: {mission.get('comTypeNm', 'N/A')}, "
            f"ID: {mission.get('contentId', 'N/A')}, "
            f"코드: {mission.get('comCd', 'N/A')})"
        )
        print(mission_details)
    
    print("------------------------------------------")

    # --- 2단계: 미션 완료 처리 시작 ---
    print(f"--- 오늘의 미션 완료 처리 시작 ---")
    
    success_count = 0
    fail_count = 0
    
    for mission in all_child_missions:
        comTypeNm = mission.get("comTypeNm")
        mission_name = mission.get("name", "이름 없는 미션")
        child_id = mission.get("childId") # 각 미션에 저장된 childId 사용
        child_nm = mission.get("childNm", "이름 없는 자녀")

        print(f"- '{mission_name}' ({comTypeNm}) / 자녀: {child_nm} (ID: {child_id}) 처리 중...")

        if not child_id:
            print(f"  [WARN] '{mission_name}' 미션에 childId가 없어 건너뜁니다.")
            fail_count += 1
            continue

        # 해당 childId에 대한 authToken 가져오기
        specific_auth_token = auth_tokens_by_child.get(child_id)

        if not specific_auth_token:
            print(f"  [WARN] childId '{child_id}'에 대한 authToken을 찾을 수 없어 '{mission_name}' 미션을 건너뜁니다.")
            fail_count += 1
            continue
        
        result = False
        # 각 헬퍼 함수에 specific_auth_token 전달
        if comTypeNm == "아람어스":
            result = _complete_aram_earth_mission(specific_auth_token, mission, server)
        elif comTypeNm == "도서관":
            result = _complete_library_mission(specific_auth_token, mission, server)
        elif comTypeNm == "위티TV":
            result = _complete_witti_tv_mission(specific_auth_token, mission, server)
        else: # 기타 "놀이터" 등
            result = _complete_witti_mew_mission(specific_auth_token, mission, server)
            
        if result:
            success_count += 1
        else:
            fail_count += 1
            
    print("------------------------------------------")
    print(f"미션 처리 완료: 성공 {success_count}개, 실패/건너뜀 {fail_count}개")


# 아람어스 학습 완료 처리 API
def _complete_aram_earth_mission(authToken, mission, server):
    try:
        url = f"https://{server}.wittiverse.com/v2/ias/school"
        params = {
            "prodId" : "PI-00000000000000001",
            "itemCd" : mission.get('itemCd'),
            "curtniSeq" : mission.get('curtniSeq'),
            "stdLtm" : 50,
            "stdScore" : 0,
            "stdTp" : "STD"
        }
        headers = {
            'Authorization': f'Bearer {authToken}'
        }

        # --- 디버깅 로그 시작 ---
        #print(f"  [DEBUG] 아람어스 요청 URL: {url}")
        #print(f"  [DEBUG] 아람어스 요청 Headers: {headers}")
        #print(f"  [DEBUG] 아람어스 요청 JSON Body: {params}")
        # --- 디버깅 로그 끝 ---

        response = requests.post(url, headers=headers, json=params, timeout=20)

        # --- 디버깅 로그 시작 ---
        #print(f"  [DEBUG] 아람어스 응답 Status Code: {response.status_code}")
        #print(f"  [DEBUG] 아람어스 응답 Body: {response.text}")
        # --- 디버깅 로그 끝 ---

        response.raise_for_status()

        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 학습 이력 등록 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 학습 이력 등록 중 예기치 않은 오류 발생: {e}")
        return None

# 도서관 학습 완료 처리 API
def _complete_library_mission(authToken, mission, server):
    try:
        url = f"https://{server}.wittiverse.com/v2/ias/school/ebook"
        params = {
            "contsId" : mission.get('contentId'),
            "stdLtm" : 1,
            "contsLtm" : 1,
            "stdTp" : "STD",
            "latestPage": 20
        }
        headers = {
            'Authorization': f'Bearer {authToken}'
        }

        # --- 디버깅 로그 시작 ---
        #print(f"  [DEBUG] 도서관 요청 URL: {url}")
        #print(f"  [DEBUG] 도서관 요청 Headers: {headers}")
        #print(f"  [DEBUG] 도서관 요청 JSON Body: {params}")
        # --- 디버깅 로그 끝 ---

        response = requests.post(url, headers=headers, json=params, timeout=20)

        # --- 디버깅 로그 시작 ---
        #print(f"  [DEBUG] 도서관 응답 Status Code: {response.status_code}")
        #print(f"  [DEBUG] 도서관 응답 Body: {response.text}")
        # --- 디버깅 로그 끝 ---

        response.raise_for_status()

        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 학습 이력 등록 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 학습 이력 등록 중 예기치 않은 오류 발생: {e}")
        return None

# 위티TV 학습 완료 처리 API
def _complete_witti_tv_mission(authToken, mission, server):
    try:
        url = f"https://{server}.wittiverse.com/v2/ias/tv"
        params = {
            "contsId" : mission.get('contentId'),
            "stdLtm" : 1,
            "contsLtm" : 1,
            "stdTp" : "STD"
        }
        headers = {
            'Authorization': f'Bearer {authToken}'
        }

        # --- 디버깅 로그 시작 ---
        #print(f"  [DEBUG] 위티TV 요청 URL: {url}")
        #print(f"  [DEBUG] 위티TV 요청 Headers: {headers}")
        #print(f"  [DEBUG] 위티TV 요청 JSON Body: {params}")
        # --- 디버깅 로그 끝 ---

        response = requests.post(url, headers=headers, json=params, timeout=20)

        # --- 디버깅 로그 시작 ---
        #print(f"  [DEBUG] 위티TV 응답 Status Code: {response.status_code}")
        #print(f"  [DEBUG] 위티TV 응답 Body: {response.text}")
        # --- 디버깅 로그 끝 ---

        response.raise_for_status()

        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 학습 이력 등록 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 학습 이력 등록 중 예기치 않은 오류 발생: {e}")
        return None

# MEW 학습 완료 처리 API
def _complete_witti_mew_mission(authToken, mission, server):
    try:
        url = f"https://{server}.wittiverse.com/v2/ias/school/playground"
        params = {
            "contsId" : mission.get('comCd'),
            "stdLtm" : 1,
            "contsLtm" : 1,
            "stdTp" : "STD"
        }
        headers = {
            'Authorization': f'Bearer {authToken}'
        }

        # --- 디버깅 로그 시작 ---
        #print(f"  [DEBUG] MEW 요청 URL: {url}")
        #print(f"  [DEBUG] MEW 요청 Headers: {headers}")
        #print(f"  [DEBUG] MEW 요청 JSON Body: {params}")
        # --- 디버깅 로그 끝 ---

        response = requests.post(url, headers=headers, json=params, timeout=20)

        # --- 디버깅 로그 시작 ---
        #print(f"  [DEBUG] MEW 응답 Status Code: {response.status_code}")
        #print(f"  [DEBUG] MEW 응답 Body: {response.text}")
        # --- 디버깅 로그 끝 ---

        response.raise_for_status()

        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 학습 이력 등록 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 학습 이력 등록 중 예기치 않은 오류 발생: {e}")
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

# 이슈 토큰 발급 API (모든 자녀의 토큰 발급) - 오늘의 미션 전용
def login_step2_for_all_children(refreshToken, childIds, server):
    """
    2차 로그인(토큰발급): 모든 자녀의 {childId: authToken} 딕셔너리를 반환
    """
    auth_tokens_by_child = {}
    
    if not childIds:
        print("[ERROR] 2차 로그인 실패: 대상 자녀 ID 목록이 비어있습니다.")
        return {} # 빈 딕셔너리 반환

    url = f"https://{server}.wittiverse.com/v2/authenticate/token/issue"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {refreshToken}",
        "X-device-info": "QW5kcm9pZC4zMzo6OlI5VFgyMDJHNUFFTTo6OlI5VFgyMDJHNUFFTTo6OktOT1g6OjpTTS1YMjE2Ojo6YXBwLjE0Ojo6"
    }

    print(f"\n--- 모든 자녀의 2차 로그인(토큰 발급) 시작 ---")
    for child_id in childIds:
        try:
            params = {"childId": child_id}
            
            print(f"  - 2차 로그인 요청 (childId: {child_id})")
            resp = requests.get(url, headers=headers, params=params, timeout=20)
            resp.raise_for_status()

            data = resp.json()
            authToken = data.get("result", {}).get("authToken")

            if authToken:
                auth_tokens_by_child[child_id] = authToken
                print(f"    -> 성공 (childId: {child_id})")
            else:
                print(f"    -> 실패: 토큰을 찾을 수 없습니다 (childId: {child_id})")
        
        except requests.exceptions.RequestException as e:
            print(f"    -> [ERROR] 2차 로그인 실패 (네트워크/서버 오류): {e} (childId: {child_id})")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"    -> [ERROR] 2차 로그인 응답 데이터 파싱 실패: {e} (childId: {child_id})")
        except Exception as e:
            print(f"    -> [ERROR] 2차 로그인 중 예기치 않은 오류 발생: {e} (childId: {child_id})")
    
    print("------------------------------------------")
    return auth_tokens_by_child

