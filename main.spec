# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from datetime import datetime
from PyInstaller.building.build_main import Analysis, PYZ, EXE

def collect_datas(dir_name):
    lst = []
    for root, _, files in os.walk(dir_name):
        for fname in files:
            src = os.path.join(root, fname)
            rel_root = os.path.relpath(root, dir_name)
            dst = os.path.join(dir_name, rel_root)
            lst.append((src, dst))
    return lst

# 1) 버튼 이미지 포함
button_datas = collect_datas('button_images')

# 2) Airtest Android 정적 리소스 포함
site_pkg = os.path.join(sys.prefix, 'Lib', 'site-packages')
apks_src = os.path.join(site_pkg, 'airtest', 'core', 'android', 'static', 'apks')
stf_src  = os.path.join(site_pkg, 'airtest', 'core', 'android', 'static', 'stf_libs')

apks_datas = collect_datas(apks_src)
# adjust destination prefix for apks
apks_datas = [
    (src, os.path.join('airtest', 'core', 'android', 'static', 'apks',
                       os.path.relpath(os.path.dirname(src), apks_src)))
    for src, _ in apks_datas
]
# airtest가 동봉한 Yosemite.apk(430)는 vendor/의 449로 대체하므로 번들에서 뺀다.
# 24MB짜리라 그냥 두면 exe에 같은 APK가 두 벌 들어간다. (airtest_patch.py 참고)
apks_datas = [
    (src, dst) for src, dst in apks_datas
    if os.path.basename(src).lower() != 'yosemite.apk'
]

stf_datas = collect_datas(stf_src)
stf_datas = [
    (src, os.path.join('airtest', 'core', 'android', 'static', 'stf_libs',
                       os.path.relpath(os.path.dirname(src), stf_src)))
    for src, _ in stf_datas
]

adb_datas = []
if os.path.isdir('adb'):
    adb_datas += collect_datas('adb')

# 3) scrcpy (디바이스 미러링) 포함
scrcpy_datas = []
if os.path.isdir('scrcpy'):
    scrcpy_datas += collect_datas('scrcpy')

# 3-1) Yosemite.apk 449 (airtest 1.4.3 배포본) 포함
#      Android 16 기기는 minicap이 불가능해 JAVACAP을 써야 하는데,
#      airtest 1.3.5가 동봉한 430으로는 JAVACAP이 실패한다.
vendor_datas = []
if os.path.isdir('vendor'):
    vendor_datas += collect_datas('vendor')

# 4) 로컬 설정(테스트 계정 기본값) 포함
#    gitignore 대상이라 없는 환경도 있으므로 존재할 때만 넣는다.
#    exe 옆에 같은 이름의 파일을 두면 그쪽이 우선 적용된다 (load_local_config 참고).
config_datas = []
if os.path.isfile('local_config.json'):
    config_datas.append(('local_config.json', '.'))

# 최종 datas 리스트
datas = button_datas + apks_datas + stf_datas + adb_datas + scrcpy_datas + vendor_datas + config_datas

a = Analysis(
    ['Main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name=f'Witti_Auto_Test_{datetime.now().strftime("%y%m%d")}',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    windowed=True,
)
