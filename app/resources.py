"""Resource loading helpers (fonts)."""

from __future__ import annotations

import os

from PySide6.QtGui import QFontDatabase

_FONT_DIR = os.path.join(os.path.dirname(__file__), "resources", "fonts")

_FONT_FILES = [
    "Exo2-SemiBold.ttf",
    "Exo2-Bold.ttf",
    "Exo2-ExtraBold.ttf",
    "Roboto-Regular.ttf",
    "Roboto-Medium.ttf",
    "Roboto-SemiBold.ttf",
    "Roboto-Bold.ttf",
    "RobotoMono-Regular.ttf",
    "RobotoMono-Medium.ttf",
    "RobotoMono-SemiBold.ttf",
]


def load_fonts() -> list[str]:
    """Register bundled fonts with Qt. Returns the list of families loaded."""
    families: list[str] = []
    for name in _FONT_FILES:
        path = os.path.join(_FONT_DIR, name)
        if not os.path.exists(path):
            continue
        fid = QFontDatabase.addApplicationFont(path)
        if fid != -1:
            families.extend(QFontDatabase.applicationFontFamilies(fid))
    return families
