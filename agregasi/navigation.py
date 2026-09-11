"""The same footer geometry, palette, and interaction states on every page."""
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from .responsive_surface import SurfaceSvgRenderer as QSvgRenderer
from PySide6.QtWidgets import QPushButton

from .typography import draw_text
from .display_preferences import CURRENT, icon_rect


FOOTER = QRect(15, 996, 1418, 82)
ITEMS = (
    ('dashboard', 'home', 'DASHBOARD'),
    ('box', 'box', 'TAHAP 1 / BOX'),
    ('carton', 'carton', 'TAHAP 2 / CARTON'),
    ('pallet', 'pallet', 'TAHAP 3 / PALLET'),
    ('revision', 'revision', 'REVISION'),
    ('send', 'upload', 'KIRIM DATA'),
    ('settings', 'settings', 'PENGATURAN'),
    ('template', 'template', 'MASTER TEMPLATE'),
)
CANVAS_TOP, CANVAS_BOTTOM = '#eff3f6', '#bad0e0'
PANEL_BORDER, PANEL_SHADOW_ALPHA = '#05233a', 60
NAVY_TOP, NAVY_BOTTOM = '#03243a', '#001b2e'
ACTIVE_TOP, ACTIVE_BOTTOM = '#07549a', '#033e77'
INACTIVE_TEXT, ACTIVE_TEXT = '#b4c0ce', '#e6effb'


def button_rect(index):
    """Eight equal columns, six-pixel gaps and eight-pixel outer insets."""
    return QRect(23 + index * 176, 1004, 170, 66)


class Navigation(QObject):
    def __init__(self, page, controls):
        super().__init__(page)
        self.page = page
        self.buttons = {}
        self.hovered = None
        self.keyboard_focus = None
        self.pressed = None
        self.icons = {}
        assets = Path(__file__).resolve().parent.parent / 'assets/svg'
        for index, (key, icon_name, label) in enumerate(ITEMS):
            button = controls.findChild(QPushButton, 'nav_' + key)
            if button is None:
                raise RuntimeError('Missing navigation control: ' + key)
            button.setGeometry(button_rect(index))
            button.setText('')
            button.setAccessibleName(label)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.setChecked(key == page.active)
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            # Interaction colour belongs to this renderer, never to page QSS.
            button.setStyleSheet('QPushButton, QPushButton:hover, QPushButton:focus, '
                                'QPushButton:pressed, QPushButton:checked {'
                                'background: transparent; border: 0; padding: 0;}')
            button.installEventFilter(self)
            self.buttons[key] = button
            svg = (assets / (icon_name + '.svg')).read_bytes()
            self.icons[(key, False)] = QSvgRenderer(svg.replace(b'#edf5ff', b'#aabacb'))
            self.icons[(key, True)] = QSvgRenderer(svg.replace(b'#edf5ff', b'#d4e4f6'))
        page.installEventFilter(self)

    def reset(self):
        """A graphics-view switch does not hide/show its embedded QWidget."""
        self.hovered = self.pressed = self.keyboard_focus = None
        self.buttons[self.page.active].setChecked(True)
        self.page.update()

    def eventFilter(self, watched, event):
        kind = event.type()
        if watched is self.page and kind in (QEvent.Type.Hide, QEvent.Type.Show):
            self.reset()
        else:
            key = next((key for key, button in self.buttons.items() if button is watched), None)
            if key is None:
                return False
            if kind == QEvent.Type.Enter:
                self.hovered = key
            elif kind == QEvent.Type.Leave:
                if self.hovered == key:
                    self.hovered = None
                self.pressed = None
            elif kind == QEvent.Type.FocusIn:
                self.keyboard_focus = key if event.reason() in (
                    Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason,
                    Qt.FocusReason.ShortcutFocusReason) else None
            elif kind == QEvent.Type.FocusOut:
                if self.keyboard_focus == key:
                    self.keyboard_focus = None
            elif kind == QEvent.Type.MouseButtonPress:
                self.pressed = key
            elif kind == QEvent.Type.MouseButtonRelease:
                self.pressed = None
            else:
                return False
        self.page.update()
        return False

    @staticmethod
    def _fill(painter, rect, top, bottom, border, radius):
        gradient = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        gradient.setColorAt(0, QColor(top))
        gradient.setColorAt(1, QColor(bottom))
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(border), 1))
        painter.drawRoundedRect(rect, radius, radius)

    def paint(self, painter):
        painter.save()
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        self._fill(painter, QRectF(FOOTER), '#032237', '#001b2c', '#315064', 5)
        for index, (key, _, label) in enumerate(ITEMS):
            active = key == self.page.active
            rect = QRectF(button_rect(index))
            top, bottom, border = (ACTIVE_TOP, ACTIVE_BOTTOM, '#115b99') if active else (NAVY_TOP, NAVY_BOTTOM, '#0c3047')
            if CURRENT['hover'] and not active and self.hovered == key:
                top, bottom, border = '#082c43', '#022036', '#1a4058'
            if self.pressed == key:
                top, bottom = ('#06457f', '#033764') if active else ('#022035', '#001929')
            self._fill(painter, rect, top, bottom, border, 4)
            self.icons[(key, active)].render(painter, icon_rect(rect.center().x() - 14, rect.top() + 9, 28) if key == 'settings' else icon_rect(rect.center().x() - 16, rect.top() + 8, 32))
            draw_text(painter, rect.left() + 6, rect.top() + 44, rect.width() - 12, 18,
                      label, 10, ACTIVE_TEXT if active else INACTIVE_TEXT, False,
                      Qt.AlignmentFlag.AlignCenter)
            if self.keyboard_focus == key:
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(QPen(QColor('#9ab6cf'), 1, Qt.PenStyle.DotLine))
                painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 3, 3)
        painter.restore()
