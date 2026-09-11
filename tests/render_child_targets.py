"""Render product binding and carton bypass controls using a temporary catalog."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication
from agregasi.app import MainWindow
from agregasi.store import Store
from agregasi.typography import ui_font
from agregasi.template_database import DatabaseSourceDialog
app=QApplication([]);app.setStyle('Fusion');app.setFont(ui_font());app.setStyleSheet((ROOT/'styles/theme.qss').read_text())
out=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'docs/child_target_previews';out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    store=Store(Path(tmp)/'catalog_fixture.db');window=MainWindow(store);window.resize(1448,1086);window.show();window.navigate('template');page=window.pages['template']
    store.db.executemany('INSERT INTO aggregation_products VALUES(?,?)',[('DEMO-A','PRODUK CHILD A'),('DEMO-B','PRODUK CHILD B')]);store.db.commit()
    def capture(name):
        app.processEvents();page.refresh_shared();page.ring_animation.setCurrentTime(page.ring_animation.duration());app.processEvents();page.grab().save(str(out/name))
    page.select_level('BOX');e=page.active_editor;e.refresh_sources();e.child_product.setCurrentIndex(next(i for i in range(e.child_product.count()) if (e.child_product.itemData(i) or {}).get('id')=='DEMO-A'));e.target_min.setValue(5);e.target_max.setValue(10);e.print_mode.setCurrentText('AUTO');e.save();capture('box.png')
    e.child_product.showPopup();app.processEvents();window.grab().save(str(out/'box_products.png'));e.child_product.hidePopup()
    page.select_level('CARTON');e=page.active_editor;e.child.setCurrentIndex(e.child.findData(page.editors['BOX'].identifier));e.target_min.setValue(6);e.target_max.setValue(12);e.save();capture('carton_via_box.png')
    e.child_mode.choices['UNIT'].click();e.child_product.setCurrentIndex(next(i for i in range(e.child_product.count()) if (e.child_product.itemData(i) or {}).get('id')=='DEMO-B'));e.target_min.setValue(10);e.target_max.setValue(24);e.print_mode.setCurrentText('MANUAL');e.save();capture('carton_direct_child.png')
    for w,h in ((1366,768),(1920,1080)):
        window.resize(w,h);app.processEvents();window.grab().save(str(out/f'carton_{w}x{h}.png'))
    window.resize(1448,1086);page.select_level('PALLET');e=page.active_editor;e.child.setCurrentIndex(e.child.findData(page.editors['CARTON'].identifier));e.target_min.setValue(8);e.target_max.setValue(16);e.save();capture('pallet.png')
    dialog=DatabaseSourceDialog(store,page,product_mode=True);dialog.show();app.processEvents();dialog.grab().save(str(out/'product_source.png'));dialog.close()
    window.navigate('carton');op=window.pages['carton'];op.template_selector.setCurrentIndex(op.template_selector.findData(page.editors['CARTON'].identifier))
    for code in ('DEMO-UNIT-01','DEMO-UNIT-02','DEMO-UNIT-03'):op.scan_input.setText(code);op.scan()
    app.processEvents();op.grab().save(str(out/'carton_session.png'))
    for e in page.editors.values():e._data_dirty=False;e.canvas.undo.setClean()
    window.close();store.close();app.processEvents()
print('Rendered child binding, exclusive carton mode, targets, print options and local session:',out)
