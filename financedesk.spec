# -*- mode: python ; coding: utf-8 -*-
# FinanceDesk v1.1 — financedesk.spec
# Commande : pyinstaller financedesk.spec

import os
from pathlib import Path

BASE = Path(SPECPATH)

a = Analysis(
    [str(BASE / 'main.py')],
    pathex=[str(BASE)],
    binaries=[],
    datas=[
        # Interface HTML + JS
        (str(BASE / 'ui' / 'FinanceDesk_v1_1.html'), 'ui'),
        (str(BASE / 'ui' / 'login.html'),             'ui'),
        (str(BASE / 'ui' / 'app.js'),                 'ui'),
        # Polices locales
        (str(BASE / 'assets' / 'fonts'),              'assets/fonts'),
    ],
    hiddenimports=[
        'webview',
        'webview.platforms.winforms',
        'bcrypt',
        'openpyxl',
        'reportlab',
        'reportlab.graphics',
        'reportlab.platypus',
        'reportlab.lib.pagesizes',
        'cryptography',
        'sqlite3',
        'smtplib',
        'email',
        'email.mime.text',
        'email.mime.multipart',
        'email.mime.base',
        'email.encoders',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'PIL'],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FinanceDesk',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,               # Pas de fenêtre console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(BASE / 'assets' / 'logo.ico'),  # Icône de l'app
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FinanceDesk',
)
