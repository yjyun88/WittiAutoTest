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


def authenticate_study_access_detailed(studentId, loginId, server, access_type="C"):
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
            "accessType": access_type,
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
        
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        
        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 런처 커리큘럼 조회 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 런처 커리큘럼 조회 중 예기치 않은 오류 발생: {e}")
        return None


# 위티월드 메인 화면 조회 API (보유 위티팡 조회)
def get_witti_app_main(authToken, server):
    try:
        url = f"https://{server}.wittiverse.com/v2/witti-app/main"
        headers = {
            'Authorization': f'Bearer {authToken}',
        }

        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 위티월드 메인 조회 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 위티월드 메인 조회 중 예기치 않은 오류 발생: {e}")
        return None


# 위티스쿨 메인 화면 조회 API
def get_witti_school_main(authToken, server):
    try:
        url = f"https://{server}.wittiverse.com/v2/witti-school/main"
        headers = {
            'Authorization': f'Bearer {authToken}',
        }

        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 위티스쿨 메인 조회 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 위티스쿨 메인 조회 중 예기치 않은 오류 발생: {e}")
        return None


# 아람북월드 과목 조회 API
def get_aram_bookworld_subject(authToken, ptnrId, prodId, server):
    try:
        url = f"https://{server}.wittiverse.com/v2/witti-school/aram-bookworld/subject"
        headers = {
            'Authorization': f'Bearer {authToken}',
        }
        params = {
            "ptnrId": ptnrId,
            "prodId": prodId,
        }

        response = requests.get(url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 아람북월드 과목 조회 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 아람북월드 과목 조회 중 예기치 않은 오류 발생: {e}")
        return None


# 학습 리포트 > 선생님 / 이 주 활동현황
def get_teacher_activity_report(authToken, childId, childAge, curriculumTp, year, month, week, server):
    try:
        url = f"https://{server}.wittiverse.com/v2/report/teacherActivityReport"
        headers = {
            'Authorization': f'Bearer {authToken}',
            'Content-Type': 'application/json',
        }
        body = {
            "curriculumTp": curriculumTp,
            "childAge": childAge,
            "childId": childId,
            "year": year,
            "month": month,
            "week": week,
            "reportType": "WEEK",
        }

        response = requests.post(url, headers=headers, json=body, timeout=20)
        response.raise_for_status()
        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 선생님 활동현황 리포트 조회 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 선생님 활동현황 리포트 조회 중 예기치 않은 오류 발생: {e}")
        return None


# 위티스쿨 도서관 메인 조회 API
def get_witti_school_ebook_main(authToken, server):
    try:
        url = f"https://{server}.wittiverse.com/v2/witti-school/e-book/main"
        headers = {
            'Authorization': f'Bearer {authToken}',
        }

        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 도서관 메인 조회 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 도서관 메인 조회 중 예기치 않은 오류 발생: {e}")
        return None


# 위티TV 메인 화면 조회 API
def get_tv_main(authToken, server):
    try:
        url = f"https://{server}.wittiverse.com/v2/tv/main"
        headers = {
            'Authorization': f'Bearer {authToken}',
        }

        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 위티TV 메인 조회 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 위티TV 메인 조회 중 예기치 않은 오류 발생: {e}")
        return None


# 출석 시간 전송 API
def post_attendance_curriculum(authToken, server, isMidNight="false"):
    try:
        url = f"https://{server}.wittiverse.com/v2/witti-app/attendance/curriculum"
        headers = {
            'Authorization': f'Bearer {authToken}',
            'Content-Type': 'application/json',
        }
        body = {
            "isMidNight": isMidNight,
        }

        response = requests.post(url, headers=headers, json=body, timeout=20)
        response.raise_for_status()
        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 출석 시간 전송 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 출석 시간 전송 중 예기치 않은 오류 발생: {e}")
        return None


# 학습 리포트 > 부모(학생) / 주간
def get_parent_report(authToken, childId, childAge, curriculumTp, year, month, week, server):
    try:
        url = f"https://{server}.wittiverse.com/v2/report/parentReport"
        headers = {
            'Authorization': f'Bearer {authToken}',
            'Content-Type': 'application/json',
        }
        body = {
            "curriculumTp": curriculumTp,
            "childAge": childAge,
            "childId": childId,
            "year": year,
            "month": month,
            "week": week,
            "reportType": "WEEK",
            "parentTp": "P",
        }

        response = requests.post(url, headers=headers, json=body, timeout=20)
        if not response.ok:
            print(f"[ERROR] 부모 리포트 {response.status_code} body={body} response={response.text[:500]}")
        return response

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 부모 리포트 조회 실패 (네트워크/서버 오류): {e}")
        return None
    except Exception as e:
        print(f"[ERROR] 부모 리포트 조회 중 예기치 않은 오류 발생: {e}")
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
