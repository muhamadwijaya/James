"""Custom buttons and clickable tiles used throughout the dashboard."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QCursor
from PySide6.QtWidgets import (
    QPushButton, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy,
    QFrame,
)

from ..theme import Color, Font
from .. import icons
from .common import make_font


class GhostButton(QPushButton):
    """Flat button with configurable accent; used for Disconnect / Restart."""

    def __init__(self, text: str, icon_name: str, parent=None, *,
                 accent: bool = False):
        super().__init__(text, parent)
        self._accent = accent
        self._icon_name = icon_name
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFont(make_font(Font.UI, 11, QFont.DemiBold))
        self.setIconSize(QSize(18, 18))
        self.setMinimumHeight(46)
        self._refresh_icon()
        self._apply_style()

    def _refresh_icon(self):
        col = Color.GREEN if self._accent else Color.TEXT_DIM
        self.setIcon(icons.icon(self._icon_name, 18, col))

    def _apply_style(self):
        if self._accent:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {Color.GREEN_SOFT};
                    color: {Color.GREEN};
                    border: 1px solid {Color.GREEN_DEEP};
                    border-radius: 11px;
                    padding: 0 22px;
                    text-align: center;
                }}
                QPushButton:hover {{ background: {Color.GREEN_GLOW};
                    border: 1px solid {Color.GREEN}; }}
                QPushButton:pressed {{ background: {Color.GREEN_SOFT}; }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background: {Color.TILE};
                    color: {Color.TEXT};
                    border: 1px solid {Color.BORDER};
                    border-radius: 11px;
                    padding: 0 22px;
                    text-align: center;
                }}
                QPushButton:hover {{ background: {Color.TILE_HOVER};
                    border: 1px solid {Color.BORDER_GREEN}; }}
                QPushButton:pressed {{ background: {Color.CARD_ALT}; }}
            """)


class PrimaryButton(QPushButton):
    """Solid green call-to-action (Read Block)."""

    def __init__(self, text: str, icon_name: str | None = None, parent=None):
        super().__init__(text, parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFont(make_font(Font.UI, 11, QFont.DemiBold))
        self.setMinimumHeight(44)
        if icon_name:
            self.setIcon(icons.icon(icon_name, 16, "#042016"))
            self.setIconSize(QSize(16, 16))
        self.setStyleSheet(f"""
            QPushButton {{
                background: {Color.GREEN};
                color: #052015;
                border: none;
                border-radius: 11px;
                padding: 0 18px;
            }}
            QPushButton:hover {{ background: {Color.GREEN_BRIGHT}; }}
            QPushButton:pressed {{ background: {Color.GREEN_DIM}; }}
        """)


class IconButton(QPushButton):
    """Small square icon-only button (console copy / expand)."""

    def __init__(self, icon_name: str, parent=None, *, tip: str = "",
                 size: int = 40, accent: bool = False):
        super().__init__(parent)
        self._name = icon_name
        self._accent = accent
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedSize(size, size)
        if tip:
            self.setToolTip(tip)
        col = "#042016" if accent else Color.TEXT_MUTED
        self.setIcon(icons.icon(icon_name, 18, col))
        self.setIconSize(QSize(18, 18))
        if accent:
            self.setStyleSheet(f"""
                QPushButton {{ background: {Color.GREEN}; border: none;
                    border-radius: 10px; }}
                QPushButton:hover {{ background: {Color.GREEN_BRIGHT}; }}
                QPushButton:pressed {{ background: {Color.GREEN_DIM}; }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{ background: {Color.INPUT};
                    border: 1px solid {Color.BORDER}; border-radius: 10px; }}
                QPushButton:hover {{ border: 1px solid {Color.BORDER_GREEN};
                    background: {Color.TILE_HOVER}; }}
            """)


class WinButton(QPushButton):
    """Frameless-window control (minimise / maximise / close)."""

    def __init__(self, icon_name: str, parent=None, *, danger: bool = False):
        super().__init__(parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedSize(30, 28)
        self.setIcon(icons.icon(icon_name, 16, Color.TEXT_MUTED))
        self.setIconSize(QSize(16, 16))
        hover = "#c0392b" if danger else Color.TILE_HOVER
        self.setStyleSheet(f"""
            QPushButton {{ background: transparent; border: none;
                border-radius: 6px; }}
            QPushButton:hover {{ background: {hover}; }}
        """)


class NavButton(QPushButton):
    """Left-rail navigation entry with active-state accent + left bar."""

    def __init__(self, icon_name: str, text: str, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._text = text
        self._active = False
        self.setCheckable(True)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(46)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(20, 0, 14, 0)
        lay.setSpacing(14)

        self._bar = QFrame(self)
        self._bar.setFixedWidth(3)
        self._bar.setStyleSheet("background: transparent; border-radius: 2px;")
        self._bar.setGeometry(0, 8, 3, 30)

        self._icon = QLabel()
        self._icon.setFixedSize(22, 22)
        self._icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._icon)

        self._label = QLabel(text)
        self._label.setFont(make_font(Font.UI, 11, QFont.Medium))
        lay.addWidget(self._label)
        lay.addStretch(1)

        self._render()
        self.toggled.connect(self._on_toggle)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._bar.setGeometry(0, 9, 3, self.height() - 18)

    def _on_toggle(self, checked: bool):
        self._active = checked
        self._render()

    def _render(self):
        if self._active:
            self._icon.setPixmap(icons.pixmap(self._icon_name, 20, Color.GREEN))
            self._label.setStyleSheet(
                f"color: {Color.GREEN}; background: transparent;")
            self._bar.setStyleSheet(
                f"background: {Color.GREEN}; border-radius: 2px;")
            self.setStyleSheet(f"""
                NavButton {{ background: {Color.GREEN_GLOW};
                    border: none; border-radius: 10px; text-align: left; }}
            """)
        else:
            self._icon.setPixmap(
                icons.pixmap(self._icon_name, 20, Color.TEXT_DIM))
            self._label.setStyleSheet(
                f"color: {Color.TEXT_DIM}; background: transparent;")
            self._bar.setStyleSheet("background: transparent;")
            self.setStyleSheet(f"""
                NavButton {{ background: transparent; border: none;
                    border-radius: 10px; text-align: left; }}
                NavButton:hover {{ background: {Color.TILE}; }}
            """)


class QuickTile(QPushButton):
    """Quick-tools tile: circular icon over a title + subtitle."""

    def __init__(self, icon_name: str, title: str, subtitle: str, parent=None):
        super().__init__(parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setMinimumHeight(150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 18, 6, 16)
        lay.setSpacing(8)
        lay.setAlignment(Qt.AlignCenter)

        circle = QLabel()
        circle.setFixedSize(56, 56)
        circle.setAlignment(Qt.AlignCenter)
        circle.setPixmap(icons.pixmap(icon_name, 25, Color.GREEN))
        circle.setStyleSheet(f"""
            background: {Color.GREEN_SOFT};
            border: 1px solid {Color.GREEN_DEEP};
            border-radius: 28px;
        """)
        lay.addWidget(circle, alignment=Qt.AlignHCenter)
        lay.addSpacing(6)

        t = QLabel(title)
        t.setAlignment(Qt.AlignHCenter)
        t.setFont(make_font(Font.UI, 11, QFont.DemiBold))
        t.setStyleSheet(f"color: {Color.TEXT}; background: transparent;")
        lay.addWidget(t)

        s = QLabel(subtitle)
        s.setAlignment(Qt.AlignHCenter)
        s.setFont(make_font(Font.UI, 9))
        s.setStyleSheet(f"color: {Color.TEXT_MUTED}; background: transparent;")
        lay.addWidget(s)

        self.setStyleSheet(f"""
            QuickTile {{ background: {Color.TILE};
                border: 1px solid {Color.BORDER}; border-radius: 12px; }}
            QuickTile:hover {{ border: 1px solid {Color.GREEN_DEEP};
                background: {Color.TILE_HOVER}; }}
        """)


class FilterPill(QPushButton):
    """Small toggle pill for the live-log filter row."""

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFont(make_font(Font.UI, 9, QFont.Medium))
        self.setFixedHeight(28)
        self.setMinimumWidth(48)
        self._render()
        self.toggled.connect(lambda _: self._render())

    def _render(self):
        if self.isChecked():
            self.setStyleSheet(f"""
                QPushButton {{ background: {Color.GREEN};
                    color: #052015; border: none; border-radius: 7px;
                    padding: 0 12px; }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{ background: {Color.TILE};
                    color: {Color.TEXT_MUTED};
                    border: 1px solid {Color.BORDER};
                    border-radius: 7px; padding: 0 12px; }}
                QPushButton:hover {{ border: 1px solid {Color.BORDER_GREEN};
                    color: {Color.TEXT_DIM}; }}
            """)


class ListItem(QPushButton):
    """Left-column tool list entry (Read Card, Write Block, ...)."""

    def __init__(self, icon_name: str, text: str, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self._active = False
        self.setCheckable(True)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFixedHeight(44)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 8, 0)
        lay.setSpacing(10)
        self._icon = QLabel()
        self._icon.setFixedSize(20, 20)
        self._icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(self._icon)
        self._label = QLabel(text)
        self._label.setFont(make_font(Font.UI, 11, QFont.Medium))
        lay.addWidget(self._label)
        lay.addStretch(1)

        self._render()
        self.toggled.connect(self._on_toggle)

    def _on_toggle(self, checked: bool):
        self._active = checked
        self._render()

    def _render(self):
        if self._active:
            self._icon.setPixmap(icons.pixmap(self._icon_name, 18, Color.GREEN))
            self._label.setStyleSheet(
                f"color: {Color.GREEN}; background: transparent;")
            self.setStyleSheet(f"""
                ListItem {{ background: {Color.GREEN_SOFT};
                    border: 1px solid {Color.GREEN_DEEP};
                    border-radius: 9px; text-align: left; }}
            """)
        else:
            self._icon.setPixmap(
                icons.pixmap(self._icon_name, 18, Color.TEXT_MUTED))
            self._label.setStyleSheet(
                f"color: {Color.TEXT_DIM}; background: transparent;")
            self.setStyleSheet(f"""
                ListItem {{ background: transparent; border: 1px solid transparent;
                    border-radius: 9px; text-align: left; }}
                ListItem:hover {{ background: {Color.TILE}; }}
            """)
