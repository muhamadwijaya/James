"""Dialogs belong to the real application window, never a graphics proxy."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QMessageBox as QtMessageBox, QFileDialog as QtFileDialog)
from .typography import ui_font

DIALOG_STYLE = '''
QDialog {background:#05283e;color:#e8f3ff;}
QLabel {color:#d5e6f5;font-size:13px;background:transparent;}
QPushButton {background:#085580;color:#eef8ff;border:1px solid #2c80a7;border-radius:5px;padding:8px 14px;font-size:12px;}
QPushButton:hover {background:#0874ab;border-color:#76c4e9;}
QPushButton:focus {border:1px solid #96d5f2;}
QPushButton[destructive="true"] {background:#8e343e;border-color:#d86673;}
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox {color:#edf5ff;background:#03263d;border:1px solid #28607d;border-radius:4px;padding:5px;}
QAbstractItemView {color:#e2eff9;background:#04283f;selection-background-color:#095c89;selection-color:white;}
'''


def dialog_parent(widget=None):
    current = widget
    while current is not None:
        proxy = current.graphicsProxyWidget()
        if proxy is not None and proxy.scene() is not None:
            views = proxy.scene().views()
            if views:
                return views[0].window()
        if current.isWindow() and proxy is None:return current
        parent = current.parentWidget()
        if parent is None:
            return current
        current = parent
    return QApplication.activeWindow()


class AppDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(dialog_parent(parent))
        self._dialog_owner=parent
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setFont(ui_font(13))
        self.setStyleSheet(DIALOG_STYLE)

    def _prepare_parent(self):
        parent=dialog_parent(self._dialog_owner)
        if parent is not self and parent is not self.parentWidget():self.setParent(parent,self.windowFlags())

    def exec(self):
        self._prepare_parent();return super().exec()

    def show(self):
        self._prepare_parent();return super().show()

    def showEvent(self, event):
        super().showEvent(event)
        screen = self.screen().availableGeometry()
        self.resize(min(self.width(),screen.width()-32), min(self.height(),screen.height()-64))
        parent = self.parentWidget()
        center = parent.frameGeometry().center() if parent else screen.center()
        self.move(max(screen.left()+8,min(center.x()-self.width()//2,screen.right()-self.width()-8)),
                  max(screen.top()+28,min(center.y()-self.height()//2,screen.bottom()-self.height()-8)))


class NotificationDialog(AppDialog):
    def __init__(self, parent, title, text, buttons, default=None):
        super().__init__(parent)
        self.setObjectName('notification_dialog')
        self.setWindowTitle(title)
        self.choice = QtMessageBox.StandardButton.Cancel
        self.setMinimumWidth(380)
        self.resize(480,200)
        layout = QVBoxLayout(self);layout.setContentsMargins(22,20,22,18);layout.setSpacing(18)
        heading = QLabel(title);heading.setWordWrap(True);heading.setStyleSheet('font-size:16px;font-weight:600;color:#f3f8ff;')
        layout.addWidget(heading)
        self.message_label = QLabel(text);self.message_label.setWordWrap(True)
        self.message_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.message_label,1)
        row = QHBoxLayout();row.setSpacing(8);row.addStretch()
        labels = [('Save','Simpan'),('Discard','Abaikan'),('Yes','Hapus' if 'hapus' in title.lower() else 'Ya'),('No','Batal'),('Ok','OK'),('Cancel','Batal'),('Close','Tutup')]
        self.buttons = {}
        for key,label in labels:
            code = getattr(QtMessageBox.StandardButton,key)
            if not buttons & code:continue
            button = QPushButton(label);button.setMinimumHeight(36);button.setAutoDefault(False)
            button.setProperty('destructive',key=='Yes' and 'hapus' in title.lower())
            button.clicked.connect(lambda checked=False,c=code:self.finish(c))
            if code==default:button.setDefault(True)
            row.addWidget(button);self.buttons[code]=button
        layout.addLayout(row)

    def finish(self, choice):
        self.choice=choice;self.accept()


class MessageBox:
    StandardButton=QtMessageBox.StandardButton
    @staticmethod
    def question(parent,title,text,buttons=None,defaultButton=None):
        buttons=buttons or (MessageBox.StandardButton.Yes|MessageBox.StandardButton.No)
        if defaultButton is None:
            defaultButton=MessageBox.StandardButton.Cancel if buttons & MessageBox.StandardButton.Cancel else MessageBox.StandardButton.No
        dialog=NotificationDialog(parent,title,text,buttons,defaultButton)
        dialog.exec()
        return dialog.choice
    @staticmethod
    def warning(parent,title,text):
        return MessageBox.question(parent,title,text,MessageBox.StandardButton.Ok,MessageBox.StandardButton.Ok)
    information=warning
    critical=warning


class FileDialog:
    @staticmethod
    def getOpenFileName(parent=None,caption='',directory='',filter=''):
        return QtFileDialog.getOpenFileName(dialog_parent(parent),caption,directory,filter,
            options=QtFileDialog.Option.DontUseNativeDialog)
    @staticmethod
    def getSaveFileName(parent=None,caption='',directory='',filter=''):
        return QtFileDialog.getSaveFileName(dialog_parent(parent),caption,directory,filter,
            options=QtFileDialog.Option.DontUseNativeDialog)
