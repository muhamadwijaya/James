"""Render the real Qt template pages and print assets for visual inspection."""
import argparse
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication
from agregasi import typography
from agregasi.app import MainWindow
from agregasi.store import Store
from agregasi.label_render import render_image, export_pdf


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, default=ROOT / 'docs/template_previews')
    out = parser.parse_args().out
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setStyle('Fusion')
    app.setFont(typography.ui_font())
    app.setStyleSheet((ROOT / 'styles/theme.qss').read_text())
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / 'data.db')
        window = MainWindow(store)
        window.resize(1448, 1086)
        window.show()
        window.navigate('template')
        page = window.pages['template']
        for level in ('BOX', 'CARTON', 'PALLET'):
            page.select_level(level)
            app.processEvents()
            page.refresh_shared()
            page.ring_animation.setCurrentTime(page.ring_animation.duration())
            app.processEvents()
            page.grab().save(str(out / (level.lower() + '.png')))
            render_image(page.active_editor.document).save(str(out / (level.lower() + '_label.png')))
            export_pdf(page.active_editor.document, out / (level.lower() + '_label.pdf'))
            assert page.active_editor.list_table.horizontalScrollBar().maximum() == 0
        editor = page.active_editor
        editor.canvas.select_ids([editor.document['elements'][1]['id']])
        app.processEvents()
        page.grab().save(str(out / 'pallet_properties.png'))
        editor.tabs.setCurrentIndex(2)
        app.processEvents()
        page.grab().save(str(out / 'pallet_data.png'))
        editor.tabs.setCurrentIndex(0)
        editor.canvas.scene.clearSelection()
        for width, height in ((1366, 768), (1920, 1080)):
            window.resize(width, height)
            app.processEvents()
            window.grab().save(str(out / f'pallet_{width}x{height}.png'))
        window.close()
        store.close()
    print('Template pages, inspector, data tab, PNG and PDF labels rendered:', out)


if __name__ == '__main__':
    main()
