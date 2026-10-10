"""Recovery tanpa kartu fisik: perintah, status, log, dan pembatalan proses."""

import json
import os
import sys
import threading
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pm3tool import recovery
from pm3tool.client import PM3Client, PM3Result
from pm3tool.process import run_process


class LiveClient:
    def __init__(self, raw="", help_text="usage: hf mf options", help_ok=True, code=0):
        self.raw = raw
        self.help_text = help_text
        self.help_ok = help_ok
        self.code = code
        self.calls = []

    def run_live(self, command, **kwargs):
        self.calls.append((command, kwargs))
        text = self.help_text if command.endswith(" -h") else self.raw
        code = (0 if self.help_ok else 1) if command.endswith(" -h") else self.code
        if kwargs.get("emit"):
            kwargs["emit"](text)
        return PM3Result(command, text, "", code)


def complete_autopwn_output():
    lines = ["[=] Loaded card UID FC8DBD7F using backdoor key A396EFA4E24F\n",
             "[=] Start FM11RF08S static encrypted nonce recovery\n"]
    for sector in range(16):
        key = "436F44506144" if sector in (1, 3, 4) else "FFFFFFFFFFFF"
        lines.append(f"[+] {sector:03} | {sector * 4 + 3:03} | {key} | 1 | {key} | 1\n")
    lines.append("[+] 032 | 131 | 8E9BB5AB3435 | 1 | 00009BE9FEEE | 1 ( * )\n")
    return "".join(lines)


def test_auto_bypasses_help_exit_codes_and_keeps_resource_directory(tmp_path):
    client = LiveClient(complete_autopwn_output(), help_ok=False)
    seen = []
    report = recovery.run_auto(client, output_dir=str(tmp_path), emit=seen.append)
    assert [call[0] for call in client.calls] == ["hf mf autopwn"]
    settings = client.calls[0][1]
    assert settings["offline"] is False
    assert settings.get("cwd") is None
    assert settings["timeout"] == 7200
    assert report["status"] == "keys_found"
    assert report["uid"] == "FC8DBD7F"
    assert len(report["keys"]) == 34
    assert report["complete_normal_sectors"]
    assert report["missing_extra"] == []
    assert report["expected_extra_sectors"] == [32]
    assert "hf mf autopwn" in "".join(seen)


def test_autopwn_skipping_unsupported_attack_is_not_a_failed_recovery(tmp_path):
    client = LiveClient("[=] Darkside not supported on this card\n" + complete_autopwn_output())
    report = recovery.run_auto(client, output_dir=str(tmp_path))
    assert report["status"] == "keys_found"
    assert report["error"] is None


@pytest.mark.parametrize("origin", ["reader", "panel"])
def test_one_click_recovery_ignores_stale_advanced_fields(tmp_path, monkeypatch, origin):
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets
    from pm3tool import gui_qt
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gui_qt.MainWindow, "on_detect", lambda self: None)
    window = gui_qt.MainWindow()
    client = LiveClient(complete_autopwn_output(), help_ok=False)
    monkeypatch.setattr(window, "_client", lambda: client)
    try:
        app.processEvents()
        panel = window.recovery_panel
        panel.advanced_toggle.setChecked(True)
        panel.method.setCurrentIndex(panel.method.findData("hardnested"))
        panel.key.setText("bad-key")
        panel.uid.setText("bad-uid")
        panel.size.setCurrentText("4k")
        panel.offline.setChecked(True)
        panel.extra.setText("invalid-options")
        panel.command.setText("hf mf hardnested -r -f missing-nonces.bin")
        panel.minutes.setValue(1)
        panel.output.setText(str(tmp_path / "advanced-folder"))
        if origin == "reader":
            button = next(button for button in window.reader_buttons if button.text().startswith("Recover Keys"))
        else:
            button = panel.auto_button
        button.click()
        assert not panel.auto_button.isEnabled()
        assert panel.stop.isEnabled()
        assert not panel.advanced_toggle.isChecked()
        assert window._worker.wait(2000)
        app.processEvents()
        assert [call[0] for call in client.calls] == ["hf mf autopwn"]
        assert panel.results.rowCount() == 34
        assert panel.last_report["complete_normal_sectors"]
        assert Path(panel.last_report["session_dir"]).parent == tmp_path / "recovery_sessions"
        assert panel.auto_button.isEnabled()
        assert not panel.stop.isEnabled()
        assert not panel.timer.isActive()
        assert "Key ditemukan" in window.statusBar().currentMessage()
        # Operasi lain tidak boleh mendapatkan ulang status recovery sebelumnya.
        panel.operation_finished(True, "Check device")
        window._set_busy(False, "Selesai: Check device")
        panel.operation_finished(True, "Check device")
        assert window.statusBar().currentMessage() == "Selesai: Check device"
    finally:
        if window._worker:
            window._worker.wait(2000)
        window.close()


def test_failed_auto_recovery_can_retry_and_status_is_not_success(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets
    from pm3tool import gui_qt
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gui_qt.MainWindow, "on_detect", lambda self: None)
    window = gui_qt.MainWindow()
    client = LiveClient("[!] Error: cannot connect to COM11\n", code=1)
    monkeypatch.setattr(window, "_client", lambda: client)
    try:
        app.processEvents()
        panel = window.recovery_panel
        panel.auto_button.click()
        assert window._worker.wait(2000)
        app.processEvents()
        assert panel.last_report["status"] == "failed"
        assert "Recovery gagal" in window.statusBar().currentMessage()
        assert "cannot connect" in panel.summary.text()
        assert panel.auto_button.isEnabled()
        client.raw = complete_autopwn_output()
        client.code = 0
        panel.auto_button.click()
        assert window._worker.wait(2000)
        app.processEvents()
        assert panel.results.rowCount() == 34
        assert "Key ditemukan" in window.statusBar().currentMessage()
        assert len(client.calls) == 2
    finally:
        if window._worker:
            window._worker.wait(2000)
        window.close()


def test_auto_executes_real_process_with_detected_com_and_streams_keys(tmp_path, monkeypatch):
    if os.name == "nt":
        pytest.skip("Fixture executable memakai shebang POSIX; Windows argv diuji terpisah.")
    from pm3tool import client as client_module
    from pm3tool.detection import SerialPort
    binary = tmp_path / "proxmark3"
    binary.write_text(f"#!{sys.executable}\nimport sys, json, os\n"
                      "print('ARGV=' + json.dumps(sys.argv[1:]), flush=True)\n"
                      "print('CWD=' + os.getcwd(), flush=True)\n"
                      "assert sys.argv[1:] == ['COM11', '-c', 'hf mf autopwn']\n"
                      f"print({complete_autopwn_output()!r}, flush=True)\n", encoding="utf-8")
    binary.chmod(0o700)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(client_module, "list_serial_ports", lambda: (SerialPort("COM11", "USB Serial Device", "VID_9AC4&PID_4B8F"),))
    client = PM3Client(binary=str(binary))
    seen = []
    report = recovery.run_auto(client, emit=seen.append)
    assert client.port == "COM11"
    assert report["complete_normal_sectors"]
    assert len(report["keys"]) == 34
    log = Path(report["session_dir"], "session.log").read_text()
    assert "CWD=" + str(tmp_path) in log
    assert seen


def test_process_deadline_still_applies_after_output_pipe_closes():
    result = run_process([sys.executable, "-c", "import os,time; os.close(1); os.close(2); time.sleep(20)"],
                         "closed-output", timeout=0.1)
    assert result.returncode == 124


def test_catalog_covers_official_recovery_section():
    expected = {"darkside", "nested", "hardnested", "staticnested", "sen", "brute", "autopwn",
                "nack", "chk", "fchk", "decrypt", "supercard", "keygen"}
    assert expected <= recovery.BY_ID.keys()
    assert len(recovery.BY_ID) == len(recovery.METHODS)


@pytest.mark.parametrize("method,options,expected", [
    ("nested", {"key": "436F44506144", "block": 4}, "hf mf nested --1k --blk 4 -a -k 436F44506144 --dump"),
    ("staticnested", {"key": "FFFFFFFFFFFF", "block": 8, "key_type": "B"}, "hf mf staticnested --1k --blk 8 -b -k FFFFFFFFFFFF --dumpkeys"),
    ("hardnested", {"key": "FFFFFFFFFFFF", "target": 12, "target_type": "B"}, "hf mf hardnested --blk 0 -a -k FFFFFFFFFFFF --tblk 12 --tb"),
    ("darkside", {"target": 12, "target_type": "B"}, "hf mf darkside --blk 12 -b"),
    ("autopwn", {"key": "436f44506144", "block": 144, "size": "4k"}, "hf mf autopwn --4k -s 33 -a -k 436F44506144"),
    ("reader", {"uid": "2C:D7:2F:90"}, "hf mf sim --1k -u 2CD72F90 -x -e"),
    ("reader_nested", {}, "hf mf sim --1k -y -e"),
    ("sen", {}, "hf mf sen"),
    ("brute", {}, "hf mf brute --1k --dump"),
])
def test_build_command_parameters(method, options, expected):
    assert recovery.build_command(recovery.BY_ID[method], **options) == expected


def test_dictionary_paths_with_spaces_and_offline_nonce_file(tmp_path):
    path = tmp_path / "my keys.dic"
    command = recovery.build_command(recovery.BY_ID["fchk"], dictionary=str(path))
    assert '-f "' + str(path) + '"' in command
    command = recovery.build_command(recovery.BY_ID["hardnested"], datafile=str(path), offline=True)
    assert command.endswith('" -r')
    assert "--tblk" not in command


@pytest.mark.parametrize("options", [{"key": "not-a-key"}, {"extra": "; hf mf wipe"}, {"extra": "x\ny"}])
def test_invalid_fields_and_command_chaining_rejected(options):
    with pytest.raises(recovery.RecoveryError):
        recovery.build_command(recovery.BY_ID["autopwn"], **options)


def test_irrelevant_old_fields_do_not_block_advanced_methods():
    assert recovery.build_command(recovery.BY_ID["sen"], key="old-invalid", uid="old-invalid") == "hf mf sen"
    with pytest.raises(recovery.RecoveryError, match="UID"):
        recovery.build_command(recovery.BY_ID["reader"], uid="123")


def test_staticnested_requires_known_key():
    with pytest.raises(recovery.RecoveryError, match="key valid"):
        recovery.build_command(recovery.BY_ID["staticnested"])


def test_parser_accepts_sector32_sen_and_reader_key_but_not_input():
    raw = """
Known key: A396EFA4E24F
[=] execute: hf mf hardnested -k FFFFFFFFFFFF
[+] Key sec 032 key B = 00009BE9FEEE | 33/34 keys
[+] Sector 15 keyA = 436F44506144
[+] Found valid key: 8e9bb5ab3435
"""
    rows, keys = recovery.parse_results(raw)
    assert rows == [{"sector": 15, "type": "A", "key": "436F44506144"},
                    {"sector": 32, "type": "B", "key": "00009BE9FEEE"}]
    assert keys == ["436F44506144", "00009BE9FEEE", "8E9BB5AB3435"]


def test_recovery_exports_partial_report_and_unique_dictionary(tmp_path):
    client = LiveClient("[+] UID: 2C D7 2F 90\n[+] Key sec 001 key A = 436F44506144\n")
    report = recovery.run_recovery(client, recovery.BY_ID["sen"], "hf mf sen", output_dir=str(tmp_path))
    assert report["status"] == "keys_found"
    assert report["uid"] == "2CD72F90"
    assert not report["complete_normal_sectors"]
    assert len(report["missing"]) == 31
    assert report["missing_extra"] == [{"sector": 32, "type": "A"}, {"sector": 32, "type": "B"}]
    session = Path(report["session_dir"])
    assert (session / "recovered.dic").read_text() == "436F44506144\n"
    assert json.loads((session / "report.json").read_text())["keys"] == report["keys"]
    assert "Recovery dimulai" in (session / "session.log").read_text()
    assert [call[0] for call in client.calls] == ["hf mf sen"]
    assert client.calls[0][1].get("cwd") is None


def test_unknown_method_with_exit_zero_reports_actual_failure(tmp_path):
    client = LiveClient("[!] Unknown command 'sen'")
    report = recovery.run_recovery(client, recovery.BY_ID["sen"], "hf mf sen", output_dir=str(tmp_path))
    assert report["status"] == "failed"
    assert len(client.calls) == 1
    assert report["unique_keys"] == []
    assert "Unknown command" in report["error"]


def test_help_key_and_command_input_do_not_count_as_recovered(tmp_path):
    client = LiveClient("Known key: FFFFFFFFFFFF\n", help_text="Found key: A0A1A2A3A4A5\nusage")
    report = recovery.run_recovery(client, recovery.BY_ID["autopwn"], "hf mf autopwn -k FFFFFFFFFFFF", output_dir=str(tmp_path))
    assert report["status"] == "no_keys"
    assert report["unique_keys"] == []


def test_single_target_hardnested_key_gets_correct_sector_and_type(tmp_path):
    report = recovery.run_recovery(LiveClient("Key found: [436F44506144]\n"), recovery.BY_ID["hardnested"],
                                   "hf mf hardnested --blk 0 -a -k FFFFFFFFFFFF --tblk 144 --tb", output_dir=str(tmp_path), size="4k")
    assert report["keys"] == [{"sector": 33, "type": "B", "key": "436F44506144"}]


def test_keygen_candidates_are_not_reported_as_recovered_keys(tmp_path):
    report = recovery.run_recovery(LiveClient("Found key: FFFFFFFFFFFF\n"), recovery.BY_ID["keygen"],
                                   "hf mf keygen -u 11223344 -k 0", output_dir=str(tmp_path))
    assert report["status"] == "completed"
    assert report["unique_keys"] == []


def test_sen_extra_sector32_is_counted_separately(tmp_path):
    report = recovery.run_recovery(LiveClient("Key sec 032 key B = 00009BE9FEEE\n"), recovery.BY_ID["sen"],
                                   "hf mf sen", output_dir=str(tmp_path))
    assert len(report["missing"]) == 32
    assert report["missing_extra"] == [{"sector": 32, "type": "A"}]
    assert report["expected_extra_sectors"] == [32]


def test_cancel_before_attack_and_timeout_status_keep_reports(tmp_path):
    event = threading.Event()
    event.set()
    report = recovery.run_recovery(LiveClient(), recovery.BY_ID["sen"], "hf mf sen", output_dir=str(tmp_path), cancel=event)
    assert report["status"] == "cancelled"
    report = recovery.run_recovery(LiveClient("Found key: FFFFFFFFFFFF\n", code=124), recovery.BY_ID["sen"],
                                   "hf mf sen", output_dir=str(tmp_path))
    assert report["status"] == "timeout"
    assert report["unique_keys"] == ["FFFFFFFFFFFF"]


def test_sniff_success_runs_trace_but_failed_sniff_does_not(tmp_path):
    client = LiveClient("Found key: FFFFFFFFFFFF\n")
    recovery.run_recovery(client, recovery.BY_ID["sniff"], "hf 14a sniff", output_dir=str(tmp_path))
    assert [item[0] for item in client.calls] == ["hf 14a sniff", "trace list -t mf"]
    client = LiveClient(code=130)
    recovery.run_recovery(client, recovery.BY_ID["sniff"], "hf 14a sniff", output_dir=str(tmp_path))
    assert len(client.calls) == 1


def test_discover_adds_commands_only_from_recovery_section():
    raw = """
--------- recovery ---------
autopwn         Automatic key recovery
futureattack   New recovery method
--------- operations ---------
wipe           Wipe card
"""
    methods = recovery.discover(LiveClient(raw))
    assert [method.id for method in methods] == ["futureattack"]


def test_live_process_streams_output_and_timeout_terminates():
    seen = []
    event = threading.Event()
    def emit(text):
        seen.append(text)
        event.set()
    result = run_process([sys.executable, "-u", "-c", "import time; print('start', flush=True); time.sleep(20)"],
                         "test", timeout=10, emit=emit, cancel=event)
    assert result.returncode == 130
    assert "start" in result.stdout
    assert seen
    result = run_process([sys.executable, "-c", "import time; time.sleep(20)"], "test", timeout=0.1)
    assert result.returncode == 124


def test_pm3_offline_run_skips_com_detection(monkeypatch):
    client = PM3Client(binary="pm3", port="COM11")
    monkeypatch.setattr(client, "available", lambda: True)
    from pm3tool import process
    calls = []
    monkeypatch.setattr(process, "run_process", lambda argv, command, **kwargs: calls.append(argv) or PM3Result(command, "", "", 0))
    client.run_live("hf mf hardnested -r -f nonces.bin", offline=True)
    assert calls == [["pm3", "-o", "-c", "hf mf hardnested -r -f nonces.bin"]]


def test_external_tool_runs_without_com_and_saves_result(tmp_path):
    import shlex
    command = "mfkey32 -c " + shlex.quote("print('Found key: 436F44506144')")
    report = recovery.run_recovery(PM3Client(binary=sys.executable), recovery.BY_ID["mfkey32"], command,
                                   executable=sys.executable, output_dir=str(tmp_path))
    assert report["status"] == "keys_found"
    assert report["unique_keys"] == ["436F44506144"]
    assert Path(report["session_dir"], "recovered.dic").read_text() == "436F44506144\n"


def test_cli_method_listing_is_offline(monkeypatch, capsys):
    from pm3tool import cli
    monkeypatch.setattr(cli, "_make_client", lambda args: pytest.fail("Listing must not open COM"))
    assert cli.main(["recovery-methods"]) == 0
    assert "sen" in capsys.readouterr().out


def test_gui_recovery_has_methods_streams_results_and_routes_reader(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets
    from pm3tool import gui_qt
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(gui_qt.MainWindow, "on_detect", lambda self: None)
    window = gui_qt.MainWindow()
    client = LiveClient("Found valid key: 436F44506144\n")
    monkeypatch.setattr(window, "_client", lambda: client)
    try:
        app.processEvents()
        panel = window.recovery_panel
        assert panel.method.count() == len(recovery.METHODS)
        panel.output.setText(str(tmp_path))
        panel.method.setCurrentIndex(panel.method.findData("sen"))
        panel.run()
        assert not panel.method.isEnabled()
        assert panel.stop.isEnabled()
        assert window._worker.wait(2000)
        app.processEvents()
        assert panel.method.isEnabled()
        assert not panel.stop.isEnabled()
        assert panel.results.item(0, 2).text() == "436F44506144"
        assert "Key ditemukan" in panel.summary.text()
        window.sim_uid_edit.setText("2C:D7:2F:90")
        window.on_recover_reader()
        assert window._worker.wait(2000)
        app.processEvents()
        assert window.tabs.currentWidget() is panel
        assert panel.selected().id == "reader"
        assert "-u 2CD72F90" in panel.command.text()
        panel.method.setCurrentIndex(panel.method.findData("nested"))
        panel.key.setText("436F44506144")
        panel.block.setValue(4)
        panel.run()
        assert window._worker.wait(2000)
        app.processEvents()
        assert "--blk 4 -a -k 436F44506144" in panel.command.text()
    finally:
        if window._worker:
            window._worker.wait(2000)
        window.close()
