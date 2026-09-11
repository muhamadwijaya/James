"""One header and one content envelope for all eight application pages.

Older page designs retain their internal coordinates. Their panels and native
controls are mapped together into BODY, independently of the common shell.
"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QTransform

BODY = QRectF(15, 83, 1080, 902)
CONTENT_SOURCES = {
    'dashboard': QRectF(BODY),
    'box': QRectF(15, 84, 1080, 906),
    'carton': QRectF(15, 84, 1080, 906),
    'pallet': QRectF(15, 84, 1080, 906),
    'revision': QRectF(15, 75, 1080, 911),
    'send': QRectF(15, 75, 1080, 906),
    'settings': QRectF(15, 75, 1092, 921),
    'template': QRectF(8, 60, 1070, 926),
}


def content_transform(key, local=False):
    source = CONTENT_SOURCES.get(key, BODY)
    transform = QTransform()
    if not local:
        transform.translate(BODY.x(), BODY.y())
    transform.scale(BODY.width() / source.width(), BODY.height() / source.height())
    if not local:
        transform.translate(-source.x(), -source.y())
    return transform


def is_content_cell(key, rect):
    """Exclude the header, persistent sidebar and navigation hit targets."""
    source = CONTENT_SOURCES.get(key, BODY)
    return (source.left() <= rect.x() < source.right()
            and source.top() <= rect.y() < source.bottom())


def paint_header(page, subtitle):
    from .navigation import CANVAS_TOP, CANVAS_BOTTOM
    from .typography import draw_text
    gradient = QLinearGradient(0, 0, 1448, 1086)
    gradient.setColorAt(0, QColor(CANVAS_TOP))
    gradient.setColorAt(1, QColor(CANVAS_BOTTOM))
    page.p.fillRect(QRectF(0, 0, 1448, 1086), gradient)
    metadata = (f"LINE: {page.store.get('line')}   •   "
                f"SHIFT: {page.store.get('shift')}   •   USER: {page.store.get('user')}")
    draw_text(page.p, 15, 3, 520, 42, 'AGREGASI', 36, '#092749', True,
              Qt.AlignmentFlag.AlignLeft)
    draw_text(page.p, 15, 42, 610, 24, subtitle, 14, '#0d2b4c', True,
              Qt.AlignmentFlag.AlignLeft)
    draw_text(page.p, 820, 12, 612, 26, metadata, 12, '#0b2c4f', True,
              Qt.AlignmentFlag.AlignRight)
    page.line(0, 68, 1448, '#8daec5')
