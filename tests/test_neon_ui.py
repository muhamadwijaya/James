"""Presentation regression: live widgets remain reachable and connected."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import pytest
pytest.importorskip('PySide6')
from PySide6 import QtWidgets
from pm3tool.gui_qt import MainWindow

def test_live_controls_and_console(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(MainWindow, 'on_detect', lambda *a, **k: None)
    w = MainWindow()
    w.show(); app.processEvents()
    try:
        for i in range(7):
            w.tabs.setCurrentIndex(i); app.processEvents()
            assert w.tabs.widget(i).findChild(QtWidgets.QScrollArea).isVisible()
        assert w.ink_panel.product.isVisible()
        assert w.ink_panel.product.parentWidget() is not w.ink_panel
        assert not w.ink_panel.write_button.isEnabled()
        w.output.setPlainText('Native console test')
        copy = next(b for b in w.findChildren(QtWidgets.QPushButton) if b.text() == 'Copy')
        copy.click()
        assert app.clipboard().text() == 'Native console test'
        clear = next(b for b in w.findChildren(QtWidgets.QPushButton) if b.text() == 'Clear')
        clear.click()
        assert w.output.toPlainText() == ''
        w.resize(1000,720); app.processEvents()
        assert w.tabs.isVisible()
        w.tabs.setCurrentWidget(w.recovery_panel)
        w.recovery_panel.advanced_toggle.setChecked(True); app.processEvents()
        assert w.recovery_panel.advanced.isVisible()
    finally:
        w.close()

def test_reference_layout_and_existing_actions(monkeypatch):
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(MainWindow, 'on_detect', lambda *a, **k: None)
    w = MainWindow(); w.show(); app.processEvents()
    try:
        w.tabs.setCurrentIndex(2); app.processEvents()
        assert all(b.isVisible() for b in w.clone_buttons)
        source_pos = w.dump_edit.mapTo(w, w.dump_edit.rect().center())
        uid_pos = w.uid_edit.mapTo(w, w.uid_edit.rect().center())
        assert source_pos.x() < uid_pos.x()  # source and destination in separate columns
        w.tabs.setCurrentIndex(6); app.processEvents()
        assert w.ink_panel.product.isVisible() and w.ink_panel.preview_button.isVisible()
        assert not w.ink_panel.write_button.isEnabled()
        w.resize(1100,800); app.processEvents()
        assert w.width() == 1100
    finally:
        w.close()


def test_dump_table_uses_same_file_and_sector_filter(monkeypatch):
    from pathlib import Path
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(MainWindow, 'on_detect', lambda *a, **k: None)
    w = MainWindow(); w.show()
    try:
        w.tabs.setCurrentIndex(1)
        path = Path(__file__).resolve().parents[1] / 'pm3tool/ink_references/hf-mf-C2A4DA95-unused.bin'
        w.view_dump_edit.setText(str(path));w.view_sectors_edit.setText('1')
        show = next(b for b in w.tabs.widget(1).findChildren(QtWidgets.QPushButton) if b.text()=='Tampilkan')
        show.click();app.processEvents()
        assert 'Sector 1' in w.view_out.toPlainText()
        assert w.neon_view_table.rowCount() == 4
        assert w.neon_view_table.item(0,0).text() == '1'
        assert w.neon_view_table.item(0,2).text() == path.read_bytes()[64:80].hex(' ').upper()
        w.view_format.setCurrentText('ASCII');show.click();app.processEvents()
        assert w.neon_view_table.isColumnHidden(2)
    finally:
        w.close()


def test_recovery_views_follow_original_model(monkeypatch, tmp_path):
    """Both reference tables show real report values and remain live after changes."""
    from pm3tool.reference_ui import update_live
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(MainWindow, 'on_detect', lambda *a, **k: None)
    w = MainWindow(); w.show(); app.processEvents()
    try:
        p = w.recovery_panel
        report = dict(status='keys_found', keys=[
            dict(sector=3,type='A',key='AABBCCDDEEFF'),
            dict(sector=3,type='B',key='112233445566')],
            unique_keys=['AABBCCDDEEFF','112233445566'],missing=[],
            missing_extra=[],expected_extra_sectors=0,session_dir=str(tmp_path))
        p.show_report(report); update_live(w); app.processEvents()
        reader = w.neon_reader_table.model()
        assert reader.rowCount() == 1
        assert reader.data(reader.index(0,1)) == 'AABBCCDDEEFF'
        assert reader.data(reader.index(0,2)) == '112233445566'
        assert reader.data(reader.index(0,3)) == 'Recovered'
        recovery = w.neon_recovery_table.model()
        assert recovery.rowCount() == 2
        assert recovery.data(recovery.index(0,3)) == 'AABBCCDDEEFF'
        assert w.neon_reader_metrics[0].text() == '2'
        # Clearing the source table clears both derived views; there are no baked rows.
        p.results.setRowCount(0); app.processEvents()
        assert reader.rowCount() == 0 and recovery.rowCount() == 0
    finally:
        w.close()
