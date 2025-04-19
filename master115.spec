from PyInstaller.building.api import PYZ, EXE
from PyInstaller.building.build_main import Analysis
import sys
from os import path

block_cipher = None

a = Analysis(
    ['run.py'], # Updated entry point to run.py
    pathex=['.'],
    binaries=[],
    datas=[
        ('master115/resources', 'master115/resources'), # Updated resources path
        ('qt_base_app/theme/theme.yaml', 'qt_base_app/theme'),
        # ('fonts', 'fonts'), # Add back if fonts are used
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'qtawesome', # Added
        'requests',
        'yaml',
        'PIL',
        'selenium',         # Added
        'webdriver_manager',# Added
        'dotenv',           # Added
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='master115', # Updated name
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, # Set to True if you need a console window for debugging
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='master115/resources/master115.ico' # Updated icon path
) 