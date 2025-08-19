# -*- mode: python ; coding: utf-8 -*-

import os
import sys
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

stf_datas = collect_datas(stf_src)
stf_datas = [
    (src, os.path.join('airtest', 'core', 'android', 'static', 'stf_libs',
                       os.path.relpath(os.path.dirname(src), stf_src)))
    for src, _ in stf_datas
]

adb_datas = []
if os.path.isdir('adb'):
    adb_datas += collect_datas('adb')

# 최종 datas 리스트
datas = button_datas + apks_datas + stf_datas + adb_datas

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
    name='Main',
    debug=False,
    strip=False,
    upx=True,
    console=False,
    windowed=True,
)
