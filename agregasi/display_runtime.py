"""Apply UI preferences without cumulative scaling or changing label dimensions."""
import re
from PySide6.QtCore import QSize
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QWidget,QAbstractButton,QTableWidget,QApplication
from .display_preferences import CURRENT
from .typography import ui_font


def scaled_style(style):
    scale=CURRENT['font_scale']/100
    style=re.sub(r'font-size\s*:\s*(\d+(?:\.\d+)?)px',lambda m:f'font-size:{max(7,round(float(m[1])*scale))}px',style)
    style=re.sub(r'border-radius\s*:\s*\d+px',lambda m:f"border-radius:{CURRENT['radius']}px",style)
    if not CURRENT['hover']:
        style=re.sub(r'[^{}]*:hover[^{}]*\{[^{}]*\}', '', style)
    return style


def apply_native_preferences(window):
    app=QApplication.instance()
    if not hasattr(app,'_display_base_style'):app._display_base_style=app.styleSheet()
    # Capture originals once. Each change is derived from those originals.
    for page in window.pages.values():
        for w in page.findChildren(QWidget):
            if w.property('_display_base_style') is None:
                w.setProperty('_display_base_style',w.styleSheet())
            if w.property('_display_base_font') is None:
                w.setProperty('_display_base_font',QFont(w.font()))
    app.setFont(ui_font());app.setStyleSheet(scaled_style(app._display_base_style))
    for page in window.pages.values():
        page.setFont(ui_font())
        for w in page.findChildren(QWidget):
            font=QFont(w.property('_display_base_font'));font.setFamily(ui_font().family())
            px=font.pixelSize() if font.pixelSize()>0 else round(font.pointSizeF()*96/72)
            font.setPixelSize(max(7,round(px*CURRENT['font_scale']/100)));font.setStyle(QFont.Style.StyleNormal);w.setFont(font)
            QWidget.setStyleSheet(w,scaled_style(w.property('_display_base_style')))
            if isinstance(w,QAbstractButton) and not w.icon().isNull():
                if w.property('_display_icon') is None:w.setProperty('_display_icon',w.iconSize())
                base=w.property('_display_icon');factor=CURRENT['icon_scale']/100
                w.setIconSize(QSize(round(base.width()*factor),round(base.height()*factor)))
            if isinstance(w,QTableWidget):
                if w.property('_display_row') is None:w.setProperty('_display_row',w.verticalHeader().defaultSectionSize())
                delta={'RAPAT':-3,'NORMAL':0,'LEGA':5}[CURRENT['density']]
                w.verticalHeader().setDefaultSectionSize(max(20,w.property('_display_row')+delta))
        page.update()

    window.pages['settings'].appearance_panel.update_preview()
