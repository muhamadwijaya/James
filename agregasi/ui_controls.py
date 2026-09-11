"""Consistent dropdown lists for both embedded pages and native dialogs."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QListView, QFrame
from PySide6.QtGui import QPalette,QColor

_root=(Path(__file__).resolve().parent.parent/'assets/svg').as_posix()
COMBO_STYLE='''
QComboBox {color:#e5f2fc;background:#042b43;border:1px solid #28607c;border-radius:4px;padding:3px 24px 3px 7px;selection-background-color:#0c5b85;}
QComboBox:hover,QComboBox:focus {border-color:#4697bf;}
QComboBox::drop-down {subcontrol-origin:border;subcontrol-position:top right;width:21px;border:0;border-left:1px solid #24566e;border-top-right-radius:4px;border-bottom-right-radius:4px;background:#06344e;}
QComboBox::down-arrow {image:url("@ROOT@/chevron_down.svg");width:8px;height:5px;}
QComboBox QAbstractItemView {background:#052c43;color:#e5f2fc;border:1px solid #367995;outline:0;selection-background-color:#0a527e;selection-color:#fff;padding:4px;}
QComboBox QAbstractItemView::item {min-height:24px;padding:3px 7px;border:0;}
QComboBox QAbstractItemView::item:selected {background:#0a527e;color:#fff;border-radius:3px;}
'''.replace('@ROOT@',_root)


class ThemedComboBox(QComboBox):
    def __init__(self,parent=None):
        super().__init__(parent)
        view=QListView(self);view.setUniformItemSizes(True)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setView(view);self.setMaxVisibleItems(8)
        self.setStyleSheet('')

    def setStyleSheet(self,style):
        super().setStyleSheet(style+'\n'+COMBO_STYLE)

    def showPopup(self):
        self.view().setMinimumHeight(max(36,min(8,self.count())*30+10))
        container=self.view().parentWidget()
        if container is not None:
            container.setObjectName('themed_combo_popup');container.setStyleSheet('QFrame#themed_combo_popup {background:#052c43;border:1px solid #367995;border-radius:4px;padding:0;}')
            palette=container.palette();palette.setColor(QPalette.ColorRole.Window,QColor('#052c43'));palette.setColor(QPalette.ColorRole.Base,QColor('#052c43'));container.setPalette(palette);container.setAutoFillBackground(True)
            if isinstance(container,QFrame):container.setFrameShape(QFrame.Shape.NoFrame)
        super().showPopup()
