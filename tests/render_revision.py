"""Capture actual dialogs and field mapping with a temporary SQLite fixture."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from agregasi.app import MainWindow
from agregasi.store import Store
from agregasi.template_page import PreviewDialog
from agregasi.template_database import DatabaseSourceDialog
from agregasi.ui_dialogs import NotificationDialog,MessageBox
from agregasi.typography import ui_font

app=QApplication([]);app.setStyle('Fusion');app.setFont(ui_font());app.setStyleSheet((ROOT/'styles/theme.qss').read_text())
out=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'docs/revision_previews';out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    store=Store(Path(tmp)/'fixture.db');window=MainWindow(store);window.resize(1448,1086);window.show();window.navigate('template');page=window.pages['template']
    page.select_level('BOX');editor=page.active_editor;editor.nie.setText('NIE-CONTOH-001');editor.apply_metadata();editor.save();app.processEvents();page.refresh_shared();page.ring_animation.setCurrentTime(page.ring_animation.duration());app.processEvents()
    page.grab().save(str(out/'box.png'))
    for level in ('BOX','PALLET'):
        editor=page.editors[level]
        dialog=PreviewDialog(page,editor.document,editor.identifier);dialog.show();app.processEvents();dialog.grab().save(str(out/('preview_'+level.lower()+'.png')))
        dialog.resize(480,360);app.processEvents();dialog.grab().save(str(out/('preview_'+level.lower()+'_small.png')));dialog.close()
    for filename,title,text,buttons in [('delete','Hapus template','Hapus template "MASTER BOX SAMPLE" dari daftar?',MessageBox.StandardButton.Yes|MessageBox.StandardButton.No),('unsaved','Perubahan belum disimpan','Simpan perubahan template sebelum melanjutkan?',MessageBox.StandardButton.Save|MessageBox.StandardButton.Discard|MessageBox.StandardButton.Cancel),('notice','Periksa data','GTIN harus 8, 12, 13, atau 14 digit.',MessageBox.StandardButton.Ok)]:
        dialog=NotificationDialog(page,title,text,buttons);dialog.show();app.processEvents();dialog.grab().save(str(out/(filename+'.png')));dialog.close()
    page.select_level('CARTON');editor=page.active_editor;editor.child.showPopup();app.processEvents();window.grab().save(str(out/'dropdown.png'));editor.child.hidePopup()
    page.select_level('BOX');editor=page.active_editor
    store.db.execute('CREATE TABLE product_fixture (product_name TEXT, gtin TEXT, nie TEXT, batch TEXT, mfg_date TEXT, exp_date TEXT, serial TEXT, quantity TEXT)')
    store.configure({'template_data_source':{'path':str(store.path),'table':'product_fixture'}})
    editor.refresh_field_schema();editor.tabs.setCurrentIndex(2);app.processEvents()
    page.grab().save(str(out/'data_mapping.png'))
    editor.data_table.scrollToBottom();app.processEvents();editor.tabs.grab().save(str(out/'missing_fields.png'))
    dialog=DatabaseSourceDialog(store,page);dialog.show();app.processEvents();dialog.grab().save(str(out/'database_source.png'));dialog.close()
    for item in page.editors.values():item._data_dirty=False;item.canvas.undo.setClean()
    window.close();store.close();app.processEvents()
print('Captured actual application dialogs and SQLite schema fixture:',out)
