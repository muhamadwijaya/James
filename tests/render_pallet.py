"""Render Pallet with real temporary BOX -> CARTON -> PALLET relations."""
import os,sys,tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from PySide6.QtCore import QPoint,QTimer
from agregasi.app import MainWindow
from agregasi.store import Store
from agregasi.template_model import default_document
from agregasi.template_database import product_choices
from agregasi.ui_dialogs import AppDialog
app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet((ROOT/'styles/theme.qss').read_text());out=ROOT/'docs/pallet_lengkap';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');window=MainWindow(store);window.navigate('pallet');window.resize(1448,1086);window.show();app.processEvents();page=window.pages['pallet'];runtime=window.aggregation_runtime
 doc=default_document('BOX');doc.update(child_product=product_choices(store)[0],aggregation_max=1);box_id=runtime.repo.save(doc)
 doc=default_document('CARTON');doc.update(child_template_id=box_id,aggregation_max=1);carton_id=runtime.repo.save(doc)
 doc=default_document('PALLET');doc.update(name='PALLET 24 CARTON',child_template_id=carton_id,aggregation_min=1,aggregation_max=24);pallet_id=runtime.repo.save(doc);codes=[]
 for i in range(28):
  b=window.pages['box'].repo.start(box_id,store.get('batch'),'10/09/2026');b=window.pages['box'].repo.scan(b['id'],f'PREVIEW-UNIT-{i+1:04}');runtime.print_result(b['id'])
  c=window.pages['carton'].repo.start(carton_id,store.get('batch'),'10/09/2026');c=window.pages['carton'].repo.scan(c['id'],b['parent_code']);runtime.print_result(c['id']);codes.append(c['parent_code'])
 for code in codes[:4]:
  r=page.repo.start(pallet_id,store.get('batch'),'10/09/2026');page.repo.scan(r['id'],code);r=page.repo.finish(r['id']);runtime.print_result(r['id']);page.repo.verify(r['id'],r['parent_code'],1)
 page.refresh();lid=page.repo.create_targets('PALLET LIST • 24 CARTON',codes[4:],product_choices(store)[0],store.get('batch'));page.refresh();page.target_list.setCurrentIndex(page.target_list.findData(lid));page.template_selector.setCurrentIndex(page.template_selector.findData(pallet_id))
 for code in codes[4:12]:page.scan_input.setText(code);page.scan()
 page.message='DATA UJI • 8 carton terhubung ke pallet tersimpan. Menunggu scan berikutnya.';app.processEvents();page.grab().save(str(out/'pallet-lengkap.png'))
 image=QImage(3840,2880,QImage.Format.Format_RGB32);p=QPainter(image);p.scale(3840/1448,2880/1086);page.render(p,QPoint());p.end();image.save(str(out/'Pallet_Lengkap_4K_v3_10.png'))
 for w,h in [(1366,768),(1920,1080)]:window.resize(w,h);app.processEvents();window.grab().save(str(out/f'pallet-{w}x{h}.png'))
 def capture_dialog():
  d=next(d for d in window.findChildren(AppDialog) if d.isVisible());d.grab().save(str(out/'pallet-target-list.png'));d.accept()
 QTimer.singleShot(80,capture_dialog);page.show_targets()
 window.close();store.close();app.processEvents()
print('Pallet rendered: native, 1366x768, 1920x1080, 4K, target list.')
