"""Capture the running saved-template gallery using temporary fixture data."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import sys
import tempfile
from copy import deepcopy
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from PySide6.QtWidgets import QApplication
from agregasi.app import MainWindow
from agregasi.store import Store
from agregasi.typography import ui_font

app=QApplication([]);app.setStyle('Fusion');app.setFont(ui_font())
app.setStyleSheet((ROOT/'styles/theme.qss').read_text())
out=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'docs/saved_gallery_previews'
out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    store=Store(Path(tmp)/'gallery_fixture.db')
    window=MainWindow(store);window.resize(1448,1086);window.show();window.navigate('template')
    page=window.pages['template']
    for level,editor in page.editors.items():
        editor.name_edit.setText(level+' UTAMA');editor.print_mode.setCurrentText('AUTO');editor.save()
        base=deepcopy(editor.document)
        for n in range(2,13):
            doc=deepcopy(base);doc['name']=f'{level} PRODUK {n:02}'
            doc['data']['product_name']=f'PRODUK CONTOH {n:02}'
            doc['data']['batch']=f'LOT-2026-{n:03}'
            page.repo.save(doc)
    def capture(name):
        app.processEvents();page.refresh_shared()
        page.ring_animation.setCurrentTime(page.ring_animation.duration());app.processEvents()
        page.grab().save(str(out/name))
    for level in ('BOX','CARTON','PALLET'):
        page.select_level(level);editor=page.active_editor;editor.refresh_list()
        capture(level.lower()+'_page_1.png')
        editor.preview_next.click();capture(level.lower()+'_page_2.png')
        editor.preview_next.click();capture(level.lower()+'_page_3.png')
    page.select_level('CARTON');editor=page.active_editor;editor.turn_preview_page(-2)
    app.processEvents()
    editor.serial_type.grab().save(str(out/'serial_radio.png'))
    editor.print_mode.grab().save(str(out/'print_radio.png'))
    for width,height in ((1366,768),(1920,1080)):
        window.resize(width,height);app.processEvents()
        window.grab().save(str(out/f'carton_{width}x{height}.png'))
    for editor in page.editors.values():editor._data_dirty=False;editor.canvas.undo.setClean()
    window.close();store.close();app.processEvents()
print('Saved gallery captures:',out)
