"""Left navigation rail with brand footer card."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QButtonGroup,
)

from ..theme import Color, Font, Metrics
from .. import brand
from .buttons import NavButton
from .common import make_font


NAV_ITEMS = [
    ("home", "Dashboard"),
    ("plug", "Connection"),
    ("nfc", "RFID / NFC Tools"),
    ("lf", "LF Tools"),
    ("hf", "HF Tools"),
    ("card", "iClass / HID"),
    ("stack", "MIFARE"),
    ("chip", "Card Emulator"),
    ("terminal", "Command Console"),
    ("file", "Logs"),
    ("gear", "Settings"),
]


class Sidebar(QWidget):
    navigated = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(Metrics.SIDEBAR_W)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 16, 14, 16)
        root.setSpacing(4)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[NavButton] = []
        for i, (icon_name, text) in enumerate(NAV_ITEMS):
            btn = NavButton(icon_name, text)
            self._group.addButton(btn, i)
            self._buttons.append(btn)
            root.addWidget(btn)
            if i in (0, 4, 7):  # subtle grouping gaps
                root.addSpacing(4)

        self._group.idClicked.connect(self.navigated.emit)
        self._buttons[0].setChecked(True)

        root.addStretch(1)
        root.addWidget(self._footer())

    def set_active(self, index: int):
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)

    def _footer(self) -> QWidget:
        card = QFrame()
        card.setObjectName("CardGreen")
        card.setStyleSheet(
            f"#CardGreen {{ background: {Color.SIDEBAR};"
            f" border: 1px solid {Color.BORDER_GREEN}; border-radius: 14px; }}")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 20, 16, 20)
        lay.setSpacing(2)
        lay.setAlignment(Qt.AlignHCenter)

        logo = QLabel()
        logo.setPixmap(brand.logo_pixmap(58))
        logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo, alignment=Qt.AlignHCenter)
        lay.addSpacing(10)

        name = QLabel("PROXMARK3")
        name.setFont(make_font(Font.DISPLAY, 15, QFont.ExtraBold, 1.0))
        name.setStyleSheet(f"color: {Color.TEXT}; background: transparent;")
        name.setAlignment(Qt.AlignCenter)
        lay.addWidget(name)

        sub = QLabel("Open Source Hardware")
        sub.setFont(make_font(Font.UI, 9))
        sub.setStyleSheet(f"color: {Color.TEXT_CYAN}; background: transparent;")
        sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(sub)
        lay.addSpacing(14)

        ver = QLabel("GUI v1.0.0")
        ver.setFont(make_font(Font.UI, 9, QFont.Medium))
        ver.setStyleSheet(f"color: {Color.TEXT_MUTED}; background: transparent;")
        ver.setAlignment(Qt.AlignCenter)
        lay.addWidget(ver)
        return card
