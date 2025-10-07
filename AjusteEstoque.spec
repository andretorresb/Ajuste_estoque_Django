# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('C:\\GIT HUB\\ajust\\web\\templates', 'templates'), ('C:\\GIT HUB\\ajust\\core', 'core'), ('C:\\GIT HUB\\ajust\\estoque', 'estoque')]
binaries = []
hiddenimports = ['django', 'django.contrib.contenttypes', 'django.contrib.auth', 'firebirdsql', 'waitress', '.venv.Lib.site-packages.django.contrib.admin.templatetags.admin_list', '.venv.Lib.site-packages.django.contrib.admin.templatetags.admin_modify', '.venv.Lib.site-packages.django.contrib.admin.templatetags.admin_urls', '.venv.Lib.site-packages.django.contrib.admin.templatetags.base', '.venv.Lib.site-packages.django.contrib.admin.templatetags.log', '.venv.Lib.site-packages.django.contrib.flatpages.templatetags.flatpages', '.venv.Lib.site-packages.django.contrib.humanize.templatetags.humanize', '.venv.Lib.site-packages.django.templatetags.cache', '.venv.Lib.site-packages.django.templatetags.i18n', '.venv.Lib.site-packages.django.templatetags.l10n', '.venv.Lib.site-packages.django.templatetags.static', '.venv.Lib.site-packages.django.templatetags.tz', '.venv.Lib.site-packages.rest_framework.templatetags.rest_framework']
tmp_ret = collect_all('django')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AjusteEstoque',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
