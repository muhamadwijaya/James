"""Reusable building blocks: cards, headers, pills, separators, labels."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame, QLabel, QHBoxLayout, QVBoxLayout, QWidget,
    QGraphicsDropShadowEffect, QSizePolicy,
)

from ..theme import Color, Font
from .. import icons


def make_font(family: str, size: int, weight: QFont.Weight = QFont.Normal,
              spacing: float = 0.0) -> QFont:
    f = QFont(family, size)
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


class Card(QFrame):
    """Rounded surface with a 1px border and a soft drop shadow."""

    def __init__(self, parent=None, *, green: bool = False, radius: int = 14):
        super().__init__(parent)
        self.setObjectName("CardGreen" if green else "Card")
        self._radius = radius
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(26)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.setGraphicsEffect(shadow)

        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(20, 16, 20, 16)
        self._root.setSpacing(13)

    def body(self) -> QVBoxLayout:
        return self._root


class CardHeader(QWidget):
    """Icon chip + title used at the top of every card."""

    def __init__(self, icon_name: str, title: str, parent=None,
                 icon_color: str = Color.GREEN):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, 22, icon_color))
        ic.setFixedSize(26, 26)
        ic.setAlignment(Qt.AlignCenter)
        lay.addWidget(ic)

        lbl = QLabel(title)
        lbl.setObjectName("CardTitle")
        lbl.setFont(make_font(Font.UI, 13, QFont.Bold))
        lay.addWidget(lbl)
        lay.addStretch(1)
        self.title_label = lbl


class VSep(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("VSep")
        self.setFixedWidth(1)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)


class HSep(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HSep")
        self.setFixedHeight(1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


def label(text: str, *, family: str = Font.UI, size: int = 10,
          weight: QFont.Weight = QFont.Normal, color: str = Color.TEXT_DIM,
          spacing: float = 0.0) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(make_font(family, size, weight, spacing))
    lbl.setStyleSheet(f"color: {color}; background: transparent;")
    return lbl
