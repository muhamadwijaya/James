"""Smoke test Qt offscreen untuk startup, pilih manual, dan deteksi ulang."""

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
from PySide6 import QtCore, QtWidgets

from pm3tool import cli, client, gui_qt
from pm3tool.detection import Connection, SerialPort


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def wait_for_worker(window, qapp):
    # Event loop: proses signal queued di thread GUI, bukan sleep.
    loop = QtCore.QEventLoop()
    QtCore.QTimer.singleShot(1000, loop.quit)
    if window._worker and window._worker.isRunning():
        window._worker.finished.connect(loop.quit)
        loop.exec()
    qapp.processEvents()
    assert window._worker is not None
    assert window._worker.wait(1000)
    qapp.processEvents()


def test_gui_startup_redetect_and_manual_port(qapp, monkeypatch):
    monkeypatch.delenv("PM3_PORT", raising=False)
    exe = r"C:\ProxSpace\pm3\proxmark3\client\proxmark3.exe"
    current = ["COM12"]

    def detect(binary, port):
        selected = port or current[0]
        return Connection(exe, selected, (SerialPort(current[0], "Proxmark3"),),
                          (f"PM3: {exe}", f"Port PM3: {selected}"))

    monkeypatch.setattr(gui_qt, "detect_connection", detect)
    monkeypatch.setattr(client, "find_pm3", lambda binary: exe)
    monkeypatch.setattr(client, "list_serial_ports", lambda: (
        SerialPort(current[0], "Proxmark3"),))
    calls = []
    monkeypatch.setattr(client.subprocess, "run", lambda argv, **kw:
                        calls.append(argv) or SimpleNamespace(returncode=0, stdout="PM3 OK", stderr=""))
    window = gui_qt.MainWindow()
    try:
        qapp.processEvents()  # startup memulai auto-detect
        wait_for_worker(window, qapp)
        assert window.binary_edit.text() == exe
        assert window.port_edit.text() == "COM12"
        assert window.detect_button.isEnabled()

        current[0] = "COM19"  # USB reconnect, COM berubah sebelum klik Check
        window.on_check()
        wait_for_worker(window, qapp)
        assert calls[-1][1] == "COM19"
        assert window.port_edit.text() == "COM19"

        window.port_edit.setText("COM31")
        window.port_edit.textEdited.emit("COM31")
        window.on_check()
        wait_for_worker(window, qapp)
        assert calls[-1][1] == "COM31"

        window.detect_button.click()
        wait_for_worker(window, qapp)
        assert window.port_edit.text() == "COM19"
        assert not window._manual_port
    finally:
        if window._worker:
            window._worker.wait(2000)
        window.close()


def test_cli_gui_options_reach_window(monkeypatch):
    calls = []
    monkeypatch.setattr(gui_qt, "main", lambda **kw: calls.append(kw) or 0)
    assert cli.main(["--binary", r"C:\Custom\proxmark3.exe", "--port", "COM9", "gui"]) == 0
    assert calls == [{"binary": r"C:\Custom\proxmark3.exe", "port": "COM9"}]
