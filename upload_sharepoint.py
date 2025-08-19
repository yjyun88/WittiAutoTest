"""
upload_to_sharepoint.py

SharePlum을 사용하여 로컬 파일을 SharePoint 문서 라이브러리의
지정된 폴더에 업로드하는 스크립트 예제.

사용 방법:
    1) 필요한 패키지 설치:
        pip install shareplum requests_ntlm

    2) 아래 설정 부분(사이트 URL, 인증 정보, 로컬 파일 경로, 업로드 대상 폴더)를 수정

    3) 실행:
        python upload_to_sharepoint.py
"""

import os
import sys
import argparse
from shareplum import Site, Office365
from shareplum.site import Version
from requests_ntlm import HttpNtlmAuth
from datetime import datetime

def get_default_file_path():
    today = datetime.now().strftime("%Y.%m")
    base_dir = r"C:\Users\User\OneDrive - minigate\자동화\AutoTest.air\test_report"
    return os.path.join(base_dir, f"REPORT_{today}.xlsx")

def parse_args():
    p = argparse.ArgumentParser(
        description="SharePlum을 사용하여 SharePoint에 파일 업로드"
    )
    p.add_argument(
        '--method',
        choices=['online', 'ntlm'],
        default='online',
        help="인증 방식: 'online' (Office365) 또는 'ntlm' (온프레 NTLM)"
    )
    p.add_argument(
        '--tenant-url',
        default='https://minigate0.sharepoint.com',
        help="Office365 테넌트 URL (기본: https://minigate0.sharepoint.com)"
    )
    p.add_argument(
        '--site-path',
        default='/sites/witti',
        help="사이트 경로 (기본: /sites/witti)"
    )
    p.add_argument(
        '--username',
        required=True,
        help="사용자 이름 (Office365 로그인 또는 DOMAIN\\username)"
    )
    p.add_argument(
        '--password',
        required=True,
        help="비밀번호"
    )
    p.add_argument(
        '--folder',
        default='Shared Documents/100_New MG_위티버스/위티버스/97.QA',
        help="문서 라이브러리 내 대상 폴더 경로\n(기본: Shared Documents/100_New MG_위티버스/위티버스/97.QA)"
    )
    p.add_argument(
        '--file',
        default=get_default_file_path(),
        help="로컬 파일 경로 (예: C:\\path\\to\\file.xlsx)"
    )
    return p.parse_args()

def authenticate_office365(tenant_url, username, password, site_path):
    # Office365 인증 및 Site 객체 생성
    authcookie = Office365(tenant_url, username=username, password=password).GetCookies()
    site_url = tenant_url.rstrip('/') + site_path
    site = Site(site_url, version=Version.v2016, authcookie=authcookie)
    return site

def authenticate_ntlm(site_base_url, username, password):
    # NTLM 인증 (사내 온프레미스)
    ntlm_auth = HttpNtlmAuth(username, password)
    site = Site(site_base_url, version=Version.v2016, auth=ntlm_auth)
    return site

def upload_file(site, folder_path, local_file_path):
    # 로컬 파일 존재 여부 체크
    if not os.path.isfile(local_file_path):
        print(f"[ERROR] 파일을 찾을 수 없습니다: {local_file_path}", file=sys.stderr)
        sys.exit(1)

    # 대상 폴더 객체 얻기
    folder = site.Folder(folder_path)

    # 파일 읽어서 업로드
    with open(local_file_path, 'rb') as f:
        content = f.read()

    target_name = os.path.basename(local_file_path)
    folder.upload_file(content, target_name)
    print(f"[OK] '{local_file_path}' → '{folder_path}/{target_name}' 업로드 완료")

#SharePoint에 파일 업로드
def upload_report():
    args = parse_args()

    try:
        if args.method == 'online':
            if not args.tenant_url:
                print("[ERROR] --tenant-url 파라미터가 필요합니다.", file=sys.stderr)
                sys.exit(1)
            site = authenticate_office365(
                tenant_url=args.tenant_url,
                username=args.username,
                password=args.password,
                site_path=args.site_path
            )
        else:
            # 온프레미스 환경: site_base_url에 tenant_url 대신
            site_base = args.tenant_url or input("SharePoint 서버 URL을 입력하세요: ")
            site = authenticate_ntlm(
                site_base_url=site_base,
                username=args.username,
                password=args.password
            )
        upload_file(site, args.folder, args.file)
    
    except (KeyboardInterrupt, SystemExit):
        raise

    except Exception as e:
        print(f"[ERROR] 업로드 중 예외 발생: {e!r}", file=sys.stderr)
        sys.exit(1)
