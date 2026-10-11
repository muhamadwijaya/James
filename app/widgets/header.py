"""Top header: brand wordmark, connection status pills, device thumb, controls."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame,
)

from ..theme import Color, Font, Metrics
from .. import brand, icons
from .buttons import IconButton, WinButton
from .common import make_font, VSep


class _StatusSegment(QWidget):
    def __init__(self, primary: str, secondary: str, *,
                 dot: bool = False, p_color: str = Color.TEXT,
                 s_color: str = Color.TEXT_CYAN,
                 p_size: int = 13, p_weight=QFont.Bold, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        if dot:
            d = QLabel()
            d.setFixedSize(14, 14)
            d.setStyleSheet(
                f"background: {Color.GREEN_DOT}; border-radius: 7px;")
            lay.addWidget(d, alignment=Qt.AlignVCenter)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(1)
        p = QLabel(primary)
        p.setFont(make_font(Font.UI, p_size, p_weight))
        p.setStyleSheet(f"color: {p_color}; background: transparent;")
        s = QLabel(secondary)
        s.setFont(make_font(Font.UI, 10))
        s.setStyleSheet(f"color: {s_color}; background: transparent;")
        col.addWidget(p)
        col.addWidget(s)
        lay.addLayout(col)


class Header(QWidget):
    minimize = Signal()
    maximize = Signal()
    close = Signal()
    settings = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Header")
        self.setFixedHeight(Metrics.HEADER_H)

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 0, 16, 0)
        root.setSpacing(16)

        root.addWidget(self._wordmark())
        root.addStretch(1)
        root.addWidget(self._status_box())
        root.addStretch(1)
        root.addWidget(self._device_thumb())
        root.addSpacing(6)
        root.addLayout(self._controls())

    # -- brand wordmark (left) --
    def _wordmark(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        logo = QLabel()
        logo.setPixmap(brand.logo_pixmap(52))
        logo.setFixedSize(52, 52)
        logo.setAlignment(Qt.AlignCenter)
        lay.addWidget(logo)

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        name = QLabel("PROXMARK")
        name.setFont(make_font(Font.DISPLAY, 22, QFont.ExtraBold, 1.5))
        name.setStyleSheet(f"color: {Color.TEXT}; background: transparent;")
        three = QLabel("3")
        three.setFont(make_font(Font.DISPLAY, 22, QFont.ExtraBold, 1.5))
        three.setStyleSheet(f"color: {Color.GREEN}; background: transparent;")
        row.addWidget(name)
        row.addWidget(three)
        col.addLayout(row)

        sub = QLabel("RFID / NFC TOOLKIT")
        sub.setFont(make_font(Font.UI, 9, QFont.Medium, 2.5))
        sub.setStyleSheet(f"color: {Color.TEXT_CYAN}; background: transparent;")
        col.addWidget(sub)
        lay.addLayout(col)
        return w

    # -- centre status box --
    def _status_box(self) -> QWidget:
        box = QFrame()
        box.setObjectName("StatusBox")
        box.setFixedHeight(62)
        lay = QHBoxLayout(box)
        lay.setContentsMargins(22, 10, 24, 10)
        lay.setSpacing(22)

        lay.addWidget(_StatusSegment(
            "PM3 Connected", "Proxmark3 RDV4", dot=True,
            p_color=Color.GREEN, s_color=Color.TEXT_CYAN))
        sep1 = VSep(); sep1.setFixedHeight(34)
        lay.addWidget(sep1)
        lay.addWidget(_StatusSegment(
            "USB", "COM Port: COM5", p_color=Color.TEXT,
            s_color=Color.TEXT_CYAN, p_size=11, p_weight=QFont.DemiBold))
        sep2 = VSep(); sep2.setFixedHeight(34)
        lay.addWidget(sep2)

        fw = QWidget()
        fwl = QHBoxLayout(fw)
        fwl.setContentsMargins(0, 0, 0, 0)
        fwl.setSpacing(8)
        lab = QLabel("Firmware:")
        lab.setFont(make_font(Font.UI, 11))
        lab.setStyleSheet(f"color: {Color.TEXT_MUTED}; background: transparent;")
        val = QLabel("4.19341")
        val.setFont(make_font(Font.UI, 11, QFont.DemiBold))
        val.setStyleSheet(f"color: {Color.TEXT}; background: transparent;")
        fwl.addWidget(lab)
        fwl.addWidget(val)
        lay.addWidget(fw)
        return box

    # -- device thumbnail (right) --
    def _device_thumb(self) -> QWidget:
        thumb = QFrame()
        thumb.setObjectName("DeviceThumb")
        thumb.setFixedSize(118, 60)
        lay = QVBoxLayout(thumb)
        lay.setContentsMargins(6, 4, 6, 4)
        img = QLabel()
        img.setPixmap(brand.device_pixmap(104, 50))
        img.setAlignment(Qt.AlignCenter)
        lay.addWidget(img)
        return thumb

    # -- controls (settings + window buttons) --
    def _controls(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(2)
        mn = WinButton("min"); mn.clicked.connect(self.minimize.emit)
        mx = WinButton("max"); mx.clicked.connect(self.maximize.emit)
        cl = WinButton("close", danger=True); cl.clicked.connect(self.close.emit)
        top.addStretch(1)
        top.addWidget(mn)
        top.addWidget(mx)
        top.addWidget(cl)
        col.addLayout(top)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(2)
        gear = IconButton("gear", tip="Settings", size=32)
        gear.clicked.connect(self.settings.emit)
        bottom.addStretch(1)
        bottom.addWidget(gear)
        col.addLayout(bottom)
        col.addStretch(1)
        return col
