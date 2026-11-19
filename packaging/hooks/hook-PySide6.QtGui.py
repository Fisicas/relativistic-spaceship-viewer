"""Use PyInstaller's Qt discovery, excluding the unused virtual keyboard.

The widget application uses native Windows keyboard input. The optional
Qt Virtual Keyboard plugin is distributed under different license terms and
would also pull in unused QML/Quick libraries. Filter the plugin before binary
dependency analysis; do not delete dependent DLLs from a completed build.
See https://doc.qt.io/qt-6/qtvirtualkeyboard-index.html.
"""
from pathlib import Path
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [(source, target) for source, target in binaries
            if 'virtualkeyboard' not in Path(source).name.lower()]
