"""Render four pages side by side to check the shared dashboard frame."""
import os, sys, tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter,QColor
from PySide6.QtCore import QPoint,Qt
from agregasi.app import MainWindow
from agregasi.store import Store
app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet((ROOT/'styles/theme.qss').read_text())
out=ROOT/'docs/sidebar_tetap';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');window=MainWindow(store);window.show();app.processEvents()
 sheet=QImage(2896,2172,QImage.Format.Format_RGB32);sheet.fill(QColor('#dceaf3'));painter=QPainter(sheet)
 for i,key in enumerate(('template','settings','send','revision')):
  window.navigate(key);app.processEvents();page=window.pages[key]
  page.grab().save(str(out/(key+'.png')))
  painter.drawPixmap((i%2)*1448,(i//2)*1086,page.grab())
 painter.end();sheet.save(str(out/'Sidebar_Tetap_v3_7_1.png'))
 window.close();store.close();app.processEvents()
