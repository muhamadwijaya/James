"""Shared outer dashboard bounds on the 1448 x 1086 design canvas."""
from functools import wraps
from PySide6.QtCore import QRectF
from PySide6.QtGui import QTransform

SIDEBAR = (1106, 74, 328, 912)
TEMPLATE_SOURCE = (1088, 60, 350, 926)
SETTINGS_SOURCE = (1126, 75, 309, 913)

def sidebar_transform(source):
    x, y, w, h = SIDEBAR
    sx, sy, sw, sh = source
    transform = QTransform()
    transform.translate(x, y)
    transform.scale(w / sw, h / sh)
    transform.translate(-sx, -sy)
    return transform

def map_sidebar_rect(rect, source):
    return sidebar_transform(source).mapRect(QRectF(rect)).toRect()

def remap_sidebar_controls(widgets, source):
    for widget in widgets:
        widget.setGeometry(map_sidebar_rect(widget.geometry(), source))

def fixed_sidebar(source=SIDEBAR):
    """Paint a fixed frame; map page-specific contents into that frame."""
    def decorate(paint):
        @wraps(paint)
        def wrapped(self):
            self.panel(*SIDEBAR)
            self.p.save()
            try:
                self.p.setTransform(sidebar_transform(source), True)
                return paint(self)
            finally:
                self.p.restore()
        return wrapped
    return decorate
