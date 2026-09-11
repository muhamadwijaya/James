"""Shared surfaces and short interaction transitions for the template screen."""
from PySide6.QtCore import QRectF, Qt, QVariantAnimation, QEasingCurve
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QPushButton
from .typography import ui_font
from .display_preferences import CURRENT

PALETTES = {
    'blue': ('#087fd6', '#03447e', '#2088c8'),
    'green': ('#258f30', '#075427', '#31944c'),
    'red': ('#dc2827', '#8a131b', '#cd4241'),
    'gold': ('#c68c0d', '#785000', '#b68720'),
    'navy': ('#063550', '#012237', '#19516f'),
}


def surface(painter, rect, palette='navy', hover=0, pressed=False):
    top, bottom, edge = (QColor(c) for c in PALETTES[palette])
    if not CURRENT['hover']:hover=0
    if hover:
        top = top.lighter(int(100 + hover * 22))
        bottom = bottom.lighter(int(100 + hover * 18))
    if pressed:
        top, bottom = bottom, top.darker(115)
    gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    gradient.setColorAt(0, top); gradient.setColorAt(1, bottom)
    painter.setBrush(gradient); painter.setPen(QPen(edge, 1))
    painter.drawRoundedRect(rect, 4, 4)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.setPen(QPen(QColor(170, 224, 255, 30 + int(25 * hover)), 1))
    painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 3, 3)


class GlassButton(QPushButton):
    def __init__(self, text='', parent=None, palette='blue', font_size=10):
        super().__init__(text, parent)
        self.palette = palette; self.font_size = font_size; self.hover = 0.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet('QPushButton {background:transparent;border:0;padding:0;}')
        self.fade = QVariantAnimation(self); self.fade.setDuration(130)
        self.fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.fade.valueChanged.connect(self._animate)

    def _animate(self, value):
        self.hover = float(value); self.update()

    def _target(self, value):
        self.fade.stop(); self.fade.setStartValue(self.hover)
        self.fade.setEndValue(value); self.fade.start()

    def enterEvent(self, event):
        self._target(1.0); super().enterEvent(event)

    def leaveEvent(self, event):
        self._target(0.0); super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        if not self.isEnabled(): painter.setOpacity(.42)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        surface(painter, rect, self.palette, self.hover, self.isDown())
        font = ui_font(self.font_size)
        painter.setFont(font)
        # Adapt font size to the actual icon + label footprint without shifting.
        icon_width = self.iconSize().width() if not self.icon().isNull() else 0
        gap = 6 if icon_width else 0
        available = max(1, self.width() - 14 - icon_width - gap)
        while painter.fontMetrics().horizontalAdvance(self.text()) > available and font.pixelSize() > 8:
            font.setPixelSize(font.pixelSize() - 1); painter.setFont(font)
        label = painter.fontMetrics().elidedText(self.text(), Qt.TextElideMode.ElideRight, available)
        width = painter.fontMetrics().horizontalAdvance(label)
        left = (self.width() - width - icon_width - gap) / 2
        if icon_width:
            self.icon().paint(painter, int(left), (self.height()-icon_width)//2, icon_width, icon_width)
        painter.setPen(QColor('#edf6ff'))
        painter.drawText(QRectF(left+icon_width+gap, 0, width+1, self.height()), int(Qt.AlignmentFlag.AlignVCenter), label)
        if self.hasFocus():
            painter.setPen(QPen(QColor('#9ad2ff'), 1)); painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(2,2,-2,-2), 3,3)
        painter.end()
