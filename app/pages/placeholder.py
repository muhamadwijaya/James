"""Generic 'coming soon' page for nav entries beyond the Dashboard.

The Dashboard is the fully-built page; the remaining destinations show a tidy
placeholder so navigation works end to end without pretending to drive hardware.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from ..theme import Color, Font
from .. import icons
from ..widgets.common import Card, make_font


class Placeholder(QWidget):
    def __init__(self, icon_name: str, title: str, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 22)

        card = Card()
        body = card.body()
        body.setAlignment(Qt.AlignCenter)
        body.addStretch(1)

        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, 54, Color.GREEN_DEEP))
        ic.setAlignment(Qt.AlignCenter)
        body.addWidget(ic)
        body.addSpacing(18)

        t = QLabel(title)
        t.setAlignment(Qt.AlignCenter)
        t.setFont(make_font(Font.UI, 18, QFont.Bold))
        t.setStyleSheet(f"color: {Color.TEXT}; background: transparent;")
        body.addWidget(t)

        s = QLabel("This section is part of the layout preview.\n"
                   "The Dashboard page is the fully designed view.")
        s.setAlignment(Qt.AlignCenter)
        s.setFont(make_font(Font.UI, 11))
        s.setStyleSheet(f"color: {Color.TEXT_MUTED}; background: transparent;")
        body.addWidget(s)
        body.addStretch(1)

        root.addWidget(card)
