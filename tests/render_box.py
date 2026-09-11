"""Render a BOX reference preview with three test scans in an isolated database."""
import os,sys,tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from PySide6.QtCore import QPoint,Qt
from agregasi.app import MainWindow
from agregasi.store import Store
app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet((ROOT/'styles/theme.qss').read_text());out=ROOT/'docs/box_lengkap';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');window=MainWindow(store);window.navigate('box');window.resize(1448,1086);window.show();app.processEvents();page=window.pages['box']
 page.template_selector.setCurrentIndex(1)
 for serial in ('UNIT2505010001','UNIT2505010002','UNIT2505010003'):
  page.scan_input.setText(serial);page.scan()
 page.message='PRATINJAU DATA UJI • 3 unit diterima dari sesi tersimpan.';app.processEvents();page.grab().save(str(out/'box-lengkap.png'))
 img=QImage(3840,2880,QImage.Format.Format_RGB32);p=QPainter(img);p.scale(3840/1448,2880/1086);page.render(p,QPoint());p.end();img.save(str(out/'Box_Lengkap_4K_v3_8.png'))
 for width,height in [(1366,768),(1920,1080)]:
  window.resize(width,height);app.processEvents();window.grab().save(str(out/f'box-{width}x{height}.png'))
 window.close();store.close();app.processEvents()
print('BOX preview rendered at native, 1366x768, 1920x1080 and 4K.')
