"""Klik entry → preview → write dan hasil GUI, dengan simulator kartu."""

import os
from datetime import date

import pytest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
pytest.importorskip('PySide6')
from PySide6 import QtCore, QtWidgets

from pm3tool import gui_qt, ink
from test_ink import Chip


@pytest.fixture(scope='module')
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def finish(window, app):
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(3000, loop.quit)
    if window._worker.isRunning():
        window._worker.finished.connect(loop.quit)
        loop.exec()
    assert window._worker.wait(3000)
    app.processEvents()


@pytest.mark.parametrize('mode', ['normal', 'gen1a'])
def test_gui_write_workflow(qapp, monkeypatch, tmp_path, mode):
    client = Chip(magic=mode == 'gen1a')
    monkeypatch.setattr(gui_qt.MainWindow, 'on_detect', lambda *a, **k: None)
    monkeypatch.setattr(gui_qt, 'PM3Client', lambda **kw: client)
    window = gui_qt.MainWindow()
    panel = window.ink_panel
    try:
        qapp.processEvents()
        assert window.tabs.tabText(window.tabs.indexOf(panel)) == 'Write Chip Ink Baru'
        assert panel.product.text() == 'BKA236T'
        assert panel.source_uid.text() == 'C2A4DA95'
        assert panel.ascii_entry.text() == '.260321!....@B..'
        assert panel.keys_table.item(1,1).text() == '436F44506144'
        assert panel.keys_table.item(2,3).text() == 'FFFFFFFFFFFF'
        assert panel.data_table.rowCount() == 64
        assert panel.keys_table.rowCount() == 16
        assert not panel.write_button.isEnabled()
        panel.mode.setCurrentIndex(panel.mode.findData(mode))
        panel.folder.setText(str(tmp_path))
        panel.preview_button.click()
        finish(window, qapp)
        assert not client.writes
        assert panel.write_button.isEnabled() and panel.plan is not None
        assert panel.preview_table.rowCount() == len(panel.plan.changes)
        panel.write_button.click()
        finish(window, qapp)
        assert 'TERVERIFIKASI' in panel.summary.text()
        assert not panel.write_button.isEnabled()
        assert panel.preview_button.isEnabled() and not panel.stop_button.isEnabled()
        assert bytes(client.data[16:]) == ink.reference('C2A4DA95').data[16:]
        assert not panel.cancel_event
        # Pilih preset kedua: entry/data/key langsung mengikuti acuan kedua.
        panel.preset.setCurrentIndex(panel.preset.findData('D2E2DC95'))
        assert panel.source_uid.text() == 'D2E2DC95'
        assert panel.data_table.item(6,1).text().startswith('00 E8 03 01')
    finally:
        if window._worker:
            window._worker.wait(3000)
        window.close()


def test_mode_or_folder_change_invalidates_preview(qapp, monkeypatch, tmp_path):
    client = Chip()
    monkeypatch.setattr(gui_qt.MainWindow, 'on_detect', lambda *a, **k: None)
    monkeypatch.setattr(gui_qt, 'PM3Client', lambda **kw: client)
    window = gui_qt.MainWindow()
    panel = window.ink_panel
    try:
        qapp.processEvents()
        panel.folder.setText(str(tmp_path))
        panel.preview_button.click()
        finish(window, qapp)
        assert panel.write_button.isEnabled()
        panel.folder.setText(str(tmp_path/'another'))
        assert panel.plan is None and not panel.write_button.isEnabled()
        panel.preview_button.click()
        finish(window, qapp)
        panel.mode.setCurrentIndex(panel.mode.findData('gen1a'))
        assert panel.plan is None and not panel.write_button.isEnabled()
        assert not client.writes
    finally:
        if window._worker:
            window._worker.wait(3000)
        window.close()


def test_failed_preview_restores_controls(qapp, monkeypatch, tmp_path):
    client = Chip()
    client.data[64] = 0x42
    monkeypatch.setattr(gui_qt.MainWindow, 'on_detect', lambda *a, **k: None)
    monkeypatch.setattr(gui_qt, 'PM3Client', lambda **kw: client)
    window = gui_qt.MainWindow()
    panel = window.ink_panel
    try:
        qapp.processEvents()
        panel.folder.setText(str(tmp_path))
        panel.preview_button.click()
        finish(window, qapp)
        assert panel.preview_button.isEnabled() and panel.preset.isEnabled()
        assert not panel.write_button.isEnabled() and panel.plan is None
        assert 'tidak kosong' in window.output.toPlainText()
        assert not client.writes
    finally:
        if window._worker:
            window._worker.wait(3000)
        window.close()


@pytest.mark.parametrize('mode', ['normal', 'gen1a'])
def test_gui_custom_code_and_calendar_are_written(qapp, monkeypatch, tmp_path, mode):
    client = Chip(magic=mode == 'gen1a')
    monkeypatch.setattr(gui_qt.MainWindow, 'on_detect', lambda *a, **k: None)
    monkeypatch.setattr(gui_qt, 'PM3Client', lambda **kw: client)
    window = gui_qt.MainWindow()
    panel = window.ink_panel
    try:
        assert not panel.product.isReadOnly()
        assert panel.date_entry.isEnabled()
        assert panel.date_entry.date() == QtCore.QDate(2026,3,21)
        assert panel.date_ascii.text() == '260321'
        panel.folder.setText(str(tmp_path))
        panel.mode.setCurrentIndex(panel.mode.findData(mode))
        panel.product.setText('BKA999T')
        panel.date_entry.setDate(QtCore.QDate(2028,2,29))
        assert panel.source.product == 'BKA999T'
        assert panel.date_ascii.text() == '280229'
        assert '280229' in panel.ascii_entry.text()
        assert panel.data_table.item(4,1).text().endswith('1C 02')
        assert panel.data_table.item(5,1).text().startswith('1D 32 38 30 32 32 39')
        assert 'belum diuji' in panel.field_note.text()
        panel.preview_button.click()
        assert not panel.product.isEnabled() and not panel.date_entry.isEnabled()
        finish(window, qapp)
        assert panel.plan.reference.customization.product == 'BKA999T'
        assert panel.plan.reference.customization.record_date == date(2028,2,29)
        assert not client.writes
        panel.write_button.click()
        finish(window, qapp)
        assert 'TERVERIFIKASI' in panel.summary.text()
        assert 'printer belum diuji' in panel.summary.text()
        assert client.data[64:71] == b'BKA999T'
        assert client.data[78:87] == bytes.fromhex('1C021D') + b'280229'
        panel.preset.setCurrentIndex(panel.preset.findData('D2E2DC95'))
        assert panel.product.text() == 'BKA236T'
        assert panel.date_ascii.text() == '260321'
        assert panel.source.customization is None
    finally:
        if window._worker:
            window._worker.wait(3000)
        window.close()


def test_custom_edits_invalidate_preview_and_invalid_code_blocks_actions(qapp, monkeypatch, tmp_path):
    client = Chip()
    monkeypatch.setattr(gui_qt.MainWindow, 'on_detect', lambda *a, **k: None)
    monkeypatch.setattr(gui_qt, 'PM3Client', lambda **kw: client)
    window = gui_qt.MainWindow()
    panel = window.ink_panel
    try:
        panel.folder.setText(str(tmp_path))
        panel.preview_button.click()
        finish(window, qapp)
        assert panel.write_button.isEnabled()
        panel.date_entry.setDate(QtCore.QDate(2027,1,2))
        assert panel.plan is None and not panel.write_button.isEnabled()
        panel.preview_button.click()
        finish(window, qapp)
        panel.product.setText('BKA888T')
        assert panel.plan is None and not panel.write_button.isEnabled()
        panel.product.clear()
        assert panel.source is None and panel.base_source is not None
        assert not panel.preview_button.isEnabled() and not panel.export_button.isEnabled()
        assert panel.data_table.rowCount() == 0
        panel.product.setText('BKA888T')
        assert panel.preview_button.isEnabled() and panel.export_button.isEnabled()
        assert panel.date_ascii.text() == '270102'
        assert not client.writes
    finally:
        if window._worker:
            window._worker.wait(3000)
        window.close()


def test_unknown_date_format_can_be_copied_but_cannot_be_edited(qapp, monkeypatch, tmp_path):
    raw = bytearray(ink.reference('C2A4DA95').data)
    raw[79] = 13
    filename = tmp_path/'unknown-date.bin'
    filename.write_bytes(raw)
    monkeypatch.setattr(gui_qt.MainWindow, 'on_detect', lambda *a, **k: None)
    window = gui_qt.MainWindow()
    panel = window.ink_panel
    try:
        panel.file.setText(str(filename))
        panel.preset.setCurrentIndex(panel.preset.findData('file'))
        assert panel.source.data == raw
        assert panel.product.isReadOnly() and not panel.date_entry.isEnabled()
        assert panel.preview_button.isEnabled()
        assert 'tanpa personalisasi' in panel.field_note.text()
        panel.preset.setCurrentIndex(panel.preset.findData('C2A4DA95'))
        assert not panel.product.isReadOnly() and panel.date_entry.isEnabled()
    finally:
        window.close()


def test_export_uses_customized_data(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(gui_qt.MainWindow, 'on_detect', lambda *a, **k: None)
    filename = tmp_path/'custom-export.bin'
    monkeypatch.setattr(QtWidgets.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(filename), ''))
    window = gui_qt.MainWindow()
    panel = window.ink_panel
    try:
        panel.product.setText('BKA444T')
        panel.date_entry.setDate(QtCore.QDate(2027,10,31))
        panel.export_button.click()
        assert filename.read_bytes() == panel.source.data
        assert filename.read_bytes()[81:87] == b'271031'
        assert (tmp_path/'custom-export-key.bin').read_bytes() == ink.keyfile(panel.base_source.data)
    finally:
        window.close()
