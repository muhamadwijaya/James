#!/usr/bin/env python3
"""
Proxmark3 RFID / NFC Toolkit -- GUI entry point.

This is a user-interface mock-up built with PySide6. It reproduces the look of
the Proxmark3 toolkit dashboard; all data shown is static sample content and no
Proxmark3 hardware is accessed or controlled.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    # High-DPI friendliness before the app is created.
    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont

    from app.resources import load_fonts
    from app.theme import Font
    from app.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Proxmark3 Toolkit")

    load_fonts()
    app.setFont(QFont(Font.UI, 10))

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
