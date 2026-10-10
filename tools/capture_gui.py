"""Capture all seven real Qt pages without sending hardware commands."""
import os,sys
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6 import QtWidgets as W,QtCore as C
from pm3tool.gui_qt import MainWindow
app=W.QApplication.instance() or W.QApplication([])
MainWindow.on_detect=lambda *a,**k:None
w=MainWindow();w.show();w.resize(1536,1024);app.processEvents()
preview=Path(__file__).resolve().parents[1]/'previews';preview.mkdir(exist_ok=True)
for i in range(7):
    w.tabs.setCurrentIndex(i);app.processEvents();app.processEvents()
    if i==1:
        w.view_dump_edit.setText(str(Path(__file__).resolve().parents[1]/'pm3tool/ink_references/hf-mf-C2A4DA95-unused.bin'));w.view_sectors_edit.setText('1-4')
        next(b for b in w.tabs.widget(i).findChildren(W.QPushButton) if b.text()=='Tampilkan').click();app.processEvents()
    w.grab().save(str(preview/f'{i}.png'))
w.resize(1100,800);w.tabs.setCurrentIndex(6);app.processEvents();w.grab().save(str(preview/'compact.png'))
w.close()
print('Captured seven native Qt pages at 1536 x 1024 and compact layout at 1100 x 800.')
