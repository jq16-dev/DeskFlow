# DeskFlow.spec — build with: pyinstaller DeskFlow.spec
block_cipher = None
a = Analysis(
    ['main.py'], pathex=['.'],
    binaries=[],
    datas=[
        ('widgets/templates', 'widgets/templates'),
        ('widgets/media', 'widgets/media'),
        ('assets', 'assets'),
        ('plugins', 'plugins'),
    ],
    hiddenimports=[
        'psutil','requests',
        'PySide6.QtCore','PySide6.QtWidgets','PySide6.QtGui',
        'winsdk.windows.media.control',
        'winsdk.windows.storage.streams',
    ],
    hookspath=[], runtime_hooks=[],
    excludes=['tkinter','matplotlib','numpy','scipy'],
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
    name='DeskFlow', debug=False,
    bootloader_ignore_signals=False,
    strip=False, upx=True, console=False,
    icon='assets/icon.ico')
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas,
    strip=False, upx=True, name='DeskFlow')
