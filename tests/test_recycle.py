"""Simulasi kartu untuk penulisan, stale backup, salah UID, dan kegagalan."""

import hashlib
import json
import os
import re
from dataclasses import replace
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pm3tool import cli, recycle
from pm3tool.client import PM3Result


def card(uid="11223344", fill=0):
    data = bytearray([fill] * 1024)
    first = bytes.fromhex(uid)
    data[:4] = first
    data[4] = first[0] ^ first[1] ^ first[2] ^ first[3]
    data[5:16] = bytes.fromhex("08 04 00 05 00 00 00 00 00 00 00")
    for sector in range(16):
        start = (sector * 4 + 3) * 16
        data[start:start + 16] = bytes.fromhex("43 6F 44 50 61 44 FF 07 80 69 43 6F 44 50 61 44")
    return bytes(data)


def keys(data, extended=False):
    a = b"".join(data[(s * 4 + 3) * 16:(s * 4 + 3) * 16 + 6] for s in range(16))
    b = b"".join(data[(s * 4 + 3) * 16 + 10:(s * 4 + 4) * 16] for s in range(16))
    return a + (b"\xAB" * 6 if extended else b"") + b + (b"\xCD" * 6 if extended else b"")


@pytest.fixture
def inputs(tmp_path):
    source, target = card("AABBCCDD", fill=0), card(fill=0x55)
    reference = tmp_path / "factory.bin"
    baseline = tmp_path / "target.bin"
    keyfile = tmp_path / "target-key.bin"
    profile = tmp_path / "profile.json"
    reference.write_bytes(source)
    baseline.write_bytes(target)
    keyfile.write_bytes(keys(target, extended=True))
    recycle.create_profile(str(reference), "4-6", str(profile))
    return reference, baseline, keyfile, profile


def plan(inputs):
    return recycle.build_plan(*map(str, inputs))


class SimulatedClient:
    def __init__(self, data, fail_block=None, corrupt_read=None, incomplete_dump=False, switch_uid=False):
        self.data = bytearray(data)
        self.calls = []
        self.fail_block = fail_block
        self.corrupt_read = corrupt_read
        self.incomplete_dump = incomplete_dump
        self.switch_uid = switch_uid
        self.writes = []

    def run(self, command, timeout=None):
        self.calls.append(command)
        if command == "hf 14a info":
            uid = "99999999" if self.switch_uid and self.writes else self.data[:4].hex().upper()
            output = f"[+] UID: {uid}\n[+] SAK: 08 [2]\n"
        elif command.startswith("hf mf dump "):
            stem = re.search(r'-f "([^\"]+)"', command)[1]
            Path(stem + ".bin").write_bytes(self.data)
            output = "[+] Succeeded in dumping all blocks\n"
            if self.incomplete_dump:
                output += "[!] Access rights prevent reading sector... 5 block... 0 ( skip )\n"
        elif command.startswith("hf mf rdbl "):
            block = int(re.search(r"--blk (\d+)", command)[1])
            data = bytes(self.data[block * 16:(block + 1) * 16])
            if block == self.corrupt_read and self.writes:
                data = bytes(16)
            output = f"[=] {block // 4:3d} | {block:3d} | {data.hex(' ').upper()} | ................\n"
        elif command.startswith("hf mf wrbl "):
            block = int(re.search(r"--blk (\d+)", command)[1])
            self.writes.append(block)
            if block == self.fail_block:
                output = "[=] data: 00 00\n[!] Write ( fail )\n"
            else:
                data = bytes.fromhex(re.search(r"-d ([0-9A-F]{32})", command)[1])
                self.data[block * 16:(block + 1) * 16] = data
                output = "[+] Write ( ok )\n"
        else:
            raise AssertionError(command)
        return PM3Result(command, output, "", 0)


def test_preview_preserves_uid_keys_and_unselected_data(inputs):
    p = plan(inputs)
    assert p.uid == "11223344"
    assert [c.block for c in p.changes] == [4, 5, 6]
    assert p.after[:16] == p.before[:16]
    assert len(p.keyfile) == 192
    for block in range(64):
        if block not in (4, 5, 6):
            assert p.after[block * 16:(block + 1) * 16] == p.before[block * 16:(block + 1) * 16]


def test_direct_copy_preserves_target_identity_and_different_keys(inputs):
    source = bytearray(inputs[0].read_bytes())
    for sector in range(16):
        start = (sector * 4 + 3) * 16
        source[start:start + 6] = b"\xFF" * 6
        source[start + 10:start + 16] = b"\xFF" * 6
    inputs[0].write_bytes(source)
    p = recycle.build_plan(*map(str, inputs[:3]))
    assert len(p.changes) == 47
    for block in range(64):
        start = block * 16
        expected = source if block != 0 and block % 4 != 3 else p.before
        assert p.after[start:start + 16] == expected[start:start + 16]


def test_direct_copy_writes_only_changed_data_and_verifies(inputs, tmp_path):
    source = bytearray(inputs[1].read_bytes())
    source[:16] = inputs[0].read_bytes()[:16]
    source[4 * 16 + 9] ^= 1
    source[20 * 16 + 2] ^= 1
    source[7 * 16:7 * 16 + 6] = b"\xFF" * 6
    inputs[0].write_bytes(source)
    p = recycle.build_plan(*map(str, inputs[:3]))
    assert [change.block for change in p.changes] == [4, 20]
    c = SimulatedClient(p.before)
    report = recycle.execute_plan(c, p, str(tmp_path / "direct backups"), p.uid)
    assert report.verified
    assert c.writes == [4, 20]
    assert bytes(c.data) == p.after
    assert (Path(report.session_dir) / "before.bin").read_bytes() == p.before
    assert (Path(report.session_dir) / "after.bin").read_bytes() == p.after


def test_direct_copy_has_no_changes_when_only_identity_and_keys_differ(inputs):
    source = bytearray(inputs[1].read_bytes())
    source[:16] = inputs[0].read_bytes()[:16]
    source[11 * 16:11 * 16 + 6] = b"\xFF" * 6
    inputs[0].write_bytes(source)
    p = recycle.build_plan(*map(str, inputs[:3]))
    assert p.changes == ()
    assert p.after == p.before


def test_partial_byte_mask_preserves_other_bytes(inputs):
    reference, _, _, profile = inputs
    obj = json.loads(profile.read_text())
    obj["block_masks"] = {"4": "FF" + "00" * 15}
    profile.write_text(json.dumps(obj))
    p = plan(inputs)
    assert p.changes[0].offsets == (0,)
    assert p.after[65:80] == p.before[65:80]


@pytest.mark.parametrize("block", [0, 3, 7, 11, 63, 64])
def test_protected_and_out_of_range_blocks_rejected(inputs, block):
    obj = json.loads(inputs[3].read_text())
    obj["block_masks"] = {str(block): "FF" * 16}
    inputs[3].write_text(json.dumps(obj))
    with pytest.raises(recycle.RecycleError, match="dilindungi"):
        plan(inputs)


@pytest.mark.parametrize("mask", ["FF", "FE" * 16, "00" * 16, "ZZ" * 16])
def test_invalid_masks_rejected(inputs, mask):
    obj = json.loads(inputs[3].read_text())
    obj["block_masks"] = {"4": mask}
    inputs[3].write_text(json.dumps(obj))
    with pytest.raises(recycle.RecycleError):
        plan(inputs)


def test_wrong_reference_hash_rejected(inputs):
    inputs[0].write_bytes(card("AABBCCDD", fill=1))
    with pytest.raises(recycle.RecycleError, match="SHA-256"):
        plan(inputs)


def test_wrong_target_key_file_rejected(inputs):
    inputs[2].write_bytes(bytes(192))
    with pytest.raises(recycle.RecycleError, match="Key file tidak cocok"):
        plan(inputs)


def test_read_only_data_block_rejected_before_hardware(inputs):
    data = bytearray(inputs[1].read_bytes())
    # Sektor 1, blok 4: C1C2C3=010 -> read-only, inverse bits valid.
    data[7 * 16 + 6:7 * 16 + 9] = bytes.fromhex("EF 07 81")
    inputs[1].write_bytes(data)
    with pytest.raises(recycle.RecycleError, match="tidak mengizinkan"):
        plan(inputs)


def test_write_backup_and_complete_readback(inputs, tmp_path):
    p = plan(inputs)
    c = SimulatedClient(p.before)
    report = recycle.execute_plan(c, p, str(tmp_path / "backup with spaces"), p.uid)
    assert report.verified
    assert report.verified_blocks == (4, 5, 6)
    assert bytes(c.data) == p.after
    assert c.writes == [4, 5, 6]
    session = Path(report.session_dir)
    assert (session / "before.bin").read_bytes() == p.before
    assert (session / "after.bin").read_bytes() == p.after
    assert json.loads((session / "journal.json").read_text())["status"] == "verified"


def test_uid_confirmation_required_before_any_calls(inputs, tmp_path):
    p = plan(inputs)
    c = SimulatedClient(p.before)
    with pytest.raises(recycle.RecycleError, match="Konfirmasi UID"):
        recycle.execute_plan(c, p, str(tmp_path), "AABBCCDD")
    assert c.calls == []


def test_wrong_live_card_stops_before_writing(inputs, tmp_path):
    p = plan(inputs)
    c = SimulatedClient(card("55667788", fill=0x55))
    with pytest.raises(recycle.RecycleError, match="UID kartu terpasang"):
        recycle.execute_plan(c, p, str(tmp_path), p.uid)
    assert c.writes == []


def test_stale_backup_stops_before_writing(inputs, tmp_path):
    p = plan(inputs)
    data = bytearray(p.before)
    data[16] = 0xFE
    c = SimulatedClient(data)
    with pytest.raises(recycle.RecycleError, match="Data kartu berubah"):
        recycle.execute_plan(c, p, str(tmp_path), p.uid)
    assert c.writes == []


def test_incomplete_dump_even_with_success_line_blocks_writes(inputs, tmp_path):
    p = plan(inputs)
    c = SimulatedClient(p.before, incomplete_dump=True)
    with pytest.raises(recycle.RecycleError, match="Backup/verifikasi penuh gagal"):
        recycle.execute_plan(c, p, str(tmp_path), p.uid)
    assert c.writes == []


def test_write_fail_even_with_exit_zero_stops_and_retains_backup(inputs, tmp_path):
    p = plan(inputs)
    c = SimulatedClient(p.before, fail_block=5)
    with pytest.raises(recycle.RecycleError, match="tidak mengonfirmasi"):
        recycle.execute_plan(c, p, str(tmp_path), p.uid)
    assert c.writes == [4, 5]
    session = next(tmp_path.glob(p.uid + "_*"))
    journal = json.loads((session / "journal.json").read_text())
    assert journal["status"] == "incomplete"
    assert journal["verified_blocks"] == [4]
    assert journal["pending_block"] == 5
    assert (session / "before.bin").read_bytes() == p.before


def test_readback_mismatch_stops_next_block(inputs, tmp_path):
    p = plan(inputs)
    # Expected reference is zero, so use a different reference for mismatch.
    inputs[0].write_bytes(card("AABBCCDD", fill=0x22))
    inputs[3].unlink()
    recycle.create_profile(str(inputs[0]), "4-6", str(inputs[3]))
    p = plan(inputs)
    c = SimulatedClient(p.before, corrupt_read=4)
    with pytest.raises(recycle.RecycleError, match="Verifikasi hasil tulis"):
        recycle.execute_plan(c, p, str(tmp_path), p.uid)
    assert c.writes == [4]


def test_card_switch_after_write_stops_next_block(inputs, tmp_path):
    p = plan(inputs)
    c = SimulatedClient(p.before, switch_uid=True)
    with pytest.raises(recycle.RecycleError, match="UID kartu terpasang"):
        recycle.execute_plan(c, p, str(tmp_path), p.uid)
    assert c.writes == [4]


def test_injected_manufacturer_block_change_rejected(inputs, tmp_path):
    p = plan(inputs)
    after = bytearray(p.after)
    after[0] ^= 1
    invalid = replace(p, after=bytes(after))
    c = SimulatedClient(p.before)
    with pytest.raises(recycle.RecycleError, match="di luar blok data"):
        recycle.execute_plan(c, invalid, str(tmp_path), p.uid)
    assert c.calls == []


def test_cli_preview_is_offline(inputs, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_make_client", lambda args: pytest.fail("Preview must stay offline"))
    argv = ["recycle", "--reference", str(inputs[0]), "--target", str(inputs[1]),
            "--keyfile", str(inputs[2]), "--profile", str(inputs[3])]
    assert cli.main(argv) == 0
    assert "11223344" in capsys.readouterr().out


def test_cli_direct_copy_preview_without_profile_is_offline(inputs, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_make_client", lambda args: pytest.fail("Preview must stay offline"))
    argv = ["recycle", "--reference", str(inputs[0]), "--target", str(inputs[1]),
            "--keyfile", str(inputs[2])]
    assert cli.main(argv) == 0
    output = capsys.readouterr().out
    assert "tanpa profil" in output
    assert "11223344" in output
    assert "Blok data yang berubah: 47" in output


def test_sparse_json_cannot_shift_block_positions(inputs):
    data = inputs[1].read_bytes()
    obj = {"blocks": {str(i + 1): data[i * 16:(i + 1) * 16].hex() for i in range(64)}}
    path = inputs[1].with_suffix(".json")
    path.write_text(json.dumps(obj))
    with pytest.raises(recycle.RecycleError, match="0–63"):
        recycle.build_plan(str(inputs[0]), str(path), str(inputs[2]), str(inputs[3]))


def test_gui_preview_invalidation_and_confirmed_write(inputs, tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets
    from pm3tool import gui_qt
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(gui_qt.MainWindow, "on_detect", lambda self: None)
    window = gui_qt.MainWindow()
    try:
        app.processEvents()
        for name, path in zip(("recycle_reference", "recycle_target", "recycle_keys", "recycle_profile"), inputs):
            getattr(window, name).setText(str(path))
        window.recycle_backup.setText(str(tmp_path / "gui backups"))
        window.on_recycle_preview()
        assert window._worker.wait(1000)
        app.processEvents()
        assert window._recycle_plan is not None
        assert window.recycle_table.rowCount() == 3
        assert window.recycle_write.isEnabled()

        # Mengganti key type membatalkan preview lama.
        window.recycle_key_type.setCurrentText("B")
        assert window._recycle_plan is None
        assert not window.recycle_write.isEnabled()
        window.recycle_key_type.setCurrentText("A")
        window.on_recycle_preview()
        assert window._worker.wait(1000)
        app.processEvents()
        p = window._recycle_plan
        client = SimulatedClient(p.before)
        monkeypatch.setattr(window, "_client", lambda: client)
        monkeypatch.setattr(gui_qt.QtWidgets.QMessageBox, "question", lambda *args: QtWidgets.QMessageBox.No)
        window.on_recycle_write()
        assert client.calls == []

        monkeypatch.setattr(gui_qt.QtWidgets.QMessageBox, "question", lambda *args: QtWidgets.QMessageBox.Yes)
        window.on_recycle_write()
        assert window._worker.wait(2000)
        app.processEvents()
        assert bytes(client.data) == p.after
        assert not window.recycle_write.isEnabled()
        assert "Penulisan data terverifikasi" in window.output.toPlainText()
    finally:
        if window._worker:
            window._worker.wait(2000)
        window.close()


def test_gui_direct_copy_preview_without_profile_and_source_change(inputs, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6 import QtWidgets
    from pm3tool import gui_qt
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    monkeypatch.setattr(gui_qt.MainWindow, "on_detect", lambda self: None)
    window = gui_qt.MainWindow()
    try:
        app.processEvents()
        for name, path in zip(("recycle_reference", "recycle_target", "recycle_keys"), inputs):
            getattr(window, name).setText(str(path))
        assert not window.recycle_profile.text()
        window.on_recycle_preview()
        assert window._worker.wait(1000)
        app.processEvents()
        assert window._recycle_plan is not None
        assert window.recycle_table.rowCount() == 47
        assert window.recycle_write.isEnabled()
        window.recycle_profile.setText(str(inputs[3]))
        assert window._recycle_plan is None
        assert not window.recycle_write.isEnabled()
        window.on_recycle_preview()
        assert window._worker.wait(1000)
        app.processEvents()
        assert window.recycle_table.rowCount() == 3
        window.recycle_reference.clear()
        assert window._recycle_plan is None
        assert not window.recycle_write.isEnabled()
    finally:
        if window._worker:
            window._worker.wait(2000)
        window.close()
