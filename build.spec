# -*- mode: python ; coding: utf-8 -*-
# Modo ONEDIR deliberadamente: validação e diagnóstico antes do ONEFILE.
from pathlib import Path
root = Path(SPECPATH)
assets = root / 'assets'
icon_path = None
if (assets / 'app_icon.ico').is_file():
    icon_path = str(assets / 'app_icon.ico')
elif (assets / 'app_icon.png').is_file():
    # Somente no build, não em tempo de execução; Pillow está no requirements-dev.
    from PIL import Image
    generated = root / 'build' / 'Epic7ShopBot_icon.ico'
    generated.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(assets / 'app_icon.png') as img:
        img.convert('RGBA').save(
            generated, format='ICO', sizes=[(16,16), (24,24), (32,32),
                                           (48,48), (64,64), (128,128), (256,256)])
    icon_path = str(generated)
a = Analysis(
    [str(root / 'main.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'templates'), 'templates')] + ([(str(assets), 'assets')] if assets.exists() else []),
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
              'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.Qt3DCore'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='Epic7ShopBot', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=False, console=False, disable_windowed_traceback=False,
          uac_admin=False, icon=icon_path)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
               name='Epic7ShopBot')
