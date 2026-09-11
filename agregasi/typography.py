"""Shared, proportional typography for painted text and native Qt controls."""
from functools import lru_cache
from .display_preferences import CURRENT

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QFontDatabase, QFontMetricsF, QPainter


@lru_cache(maxsize=1)
def available_fonts():
    return frozenset(QFontDatabase.families())


@lru_cache(maxsize=1)
def font_family():
    available = available_fonts()
    return next((name for name in ('Segoe UI', 'Inter', 'Noto Sans', 'DejaVu Sans')
                 if name in available), QFont().family())


def ui_font(size=13, bold=False):
    family = CURRENT['font_family']
    font = QFont(font_family() if family == 'OTOMATIS' or family not in available_fonts() else family)
    font.setPixelSize(max(7, round(size * CURRENT['font_scale'] / 100)))
    font.setStyle(QFont.Style.StyleNormal)
    font.setWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
    font.setStretch(QFont.Stretch.Unstretched)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


def draw_text(painter, x, y, width, height, value, size, color, bold, align,
              wrap=False):
    """Keep glyphs inside their cell without squeezing their proportions.

    Long data is elided at a readable size. Descriptions explicitly opt into
    wrapping. A small inset protects glyph bearings and anti-aliased edges.
    """
    rect = QRectF(x, y, max(0, width), max(0, height))
    from .responsive_surface import SurfacePainter, mapped_cell
    expanded=isinstance(painter,SurfacePainter)
    if expanded:rect=mapped_cell(painter,rect)
    rect=rect.adjusted(1,1,-1,-1)
    if rect.isEmpty():
        return
    from .localization import translate
    text = translate(str(value))
    font = ui_font(size, bold)
    flags = align | Qt.AlignmentFlag.AlignVCenter
    flags |= Qt.TextFlag.TextWordWrap if wrap else Qt.TextFlag.TextSingleLine
    minimum = min(font.pixelSize(), max(9, font.pixelSize() - 2))
    while True:
        metrics = QFontMetricsF(font)
        bounds = metrics.boundingRect(rect, int(flags), text)
        if (bounds.width() <= rect.width() and bounds.height() <= rect.height()) or font.pixelSize() <= minimum:
            break
        font.setPixelSize(font.pixelSize() - 1)
    if not wrap:
        text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, rect.width())
    painter.save()
    if expanded:painter.resetTransform()
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.setClipRect(rect, Qt.ClipOperation.IntersectClip)
    painter.setFont(font)
    painter.setPen(QColor(color))
    painter.drawText(rect, int(flags), text)
    painter.restore()
    return font, text, rect, flags
