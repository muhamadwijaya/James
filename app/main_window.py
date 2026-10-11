"""Frameless main window tying together sidebar, header and the page stack."""

from __future__ import annotations

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QScrollArea,
)

from .theme import Color, Metrics
from .style import build_stylesheet
from .widgets.sidebar import Sidebar, NAV_ITEMS
from .widgets.header import Header
from .pages.dashboard import Dashboard
from .pages.placeholder import Placeholder


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Proxmark3 RFID / NFC Toolkit")
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.resize(1536, 1000)
        self.setMinimumSize(1180, 760)
        self.setStyleSheet(build_stylesheet())

        self._drag_pos: QPoint | None = None

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # header spans full width
        self.header = Header()
        self.header.minimize.connect(self.showMinimized)
        self.header.maximize.connect(self._toggle_max)
        self.header.close.connect(self.close)
        outer.addWidget(self.header)

        # body: sidebar + content
        body = QWidget()
        bl = QHBoxLayout(body)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(0)

        self.sidebar = Sidebar()
        self.sidebar.navigated.connect(self._navigate)
        bl.addWidget(self.sidebar)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("Content")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.stack = QStackedWidget()
        self.stack.setObjectName("ContentInner")
        self._build_pages()
        self.scroll.setWidget(self.stack)
        bl.addWidget(self.scroll, 1)

        outer.addWidget(body, 1)

    def _build_pages(self):
        # index 0 -> Dashboard, others -> placeholders
        self.stack.addWidget(Dashboard())
        for icon_name, title in NAV_ITEMS[1:]:
            self.stack.addWidget(Placeholder(icon_name, title))

    def _navigate(self, index: int):
        self.stack.setCurrentIndex(index)
        self.scroll.verticalScrollBar().setValue(0)

    def _toggle_max(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    # --- window dragging via the header strip ---
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and e.position().y() <= Metrics.HEADER_H:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_pos is not None and e.buttons() & Qt.LeftButton \
                and not self.isMaximized():
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, e):
        if e.position().y() <= Metrics.HEADER_H:
            self._toggle_max()
