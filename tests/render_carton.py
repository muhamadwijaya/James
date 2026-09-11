"""Render Carton from real temporary Box -> Carton relationships."""
import os,sys,tempfile
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage,QPainter
from PySide6.QtCore import QPoint
from agregasi.app import MainWindow
from agregasi.store import Store
from agregasi.template_model import default_document
from agregasi.template_database import product_choices
app=QApplication([]);app.setStyle('Fusion');app.setStyleSheet((ROOT/'styles/theme.qss').read_text());out=ROOT/'docs/carton_lengkap';out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
 store=Store(Path(tmp)/'db');window=MainWindow(store);window.navigate('carton');window.resize(1448,1086);window.show();app.processEvents();page=window.pages['carton'];runtime=window.aggregation_runtime
 doc=default_document('BOX');doc.update(child_product=product_choices(store)[0],aggregation_max=1);box_id=runtime.repo.save(doc);codes=[]
 for i in range(12):
  r=window.pages['box'].repo.start(box_id,store.get('batch'),'10/09/2026');r=window.pages['box'].repo.scan(r['id'],f'PREVIEW-UNIT-{i+1:04}');runtime.print_result(r['id']);codes.append(r['parent_code'])
 doc=default_document('CARTON');doc.update(child_template_id=box_id,aggregation_max=12);carton_id=runtime.repo.save(doc);page.refresh()
 lid=page.repo.create_targets('CARTON LIST',codes,product_choices(store)[0],store.get('batch'));page.refresh();page.target_list.setCurrentIndex(page.target_list.findData(lid));page.template_selector.setCurrentIndex(page.template_selector.findData(carton_id))
 for code in codes[:5]:page.scan_input.setText(code);page.scan()
 page.message='PRATINJAU DATA UJI • 5 box terhubung ke carton tersimpan.';app.processEvents();page.grab().save(str(out/'carton-lengkap.png'))
 image=QImage(3840,2880,QImage.Format.Format_RGB32);p=QPainter(image);p.scale(3840/1448,2880/1086);page.render(p,QPoint());p.end();image.save(str(out/'Carton_Lengkap_4K_v3_9.png'))
 for w,h in [(1366,768),(1920,1080)]:window.resize(w,h);app.processEvents();window.grab().save(str(out/f'carton-{w}x{h}.png'))
 window.close();store.close();app.processEvents()
print('Carton rendered: native, 1366x768, 1920x1080, 4K.')
