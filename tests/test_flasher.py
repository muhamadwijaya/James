"""Test modul flasher & firmware — tanpa perangkat / tanpa flashing nyata."""

import os

from pm3tool import flasher, firmware


def test_missing_tool_returns_127():
    res = flasher._missing("pm3-flash-all")
    assert res.returncode == 127
    assert not res.ok
    assert "pm3-flash-all" in res.stderr


def test_flash_with_flasher_requires_a_file():
    # port diisi, tapi tanpa bootrom/fullimage harus ValueError
    try:
        flasher.flash_with_flasher("/dev/ttyACM0")
    except ValueError as exc:
        assert "bootrom" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("ValueError diharapkan")


def test_find_firmware_in_empty_dir(tmp_path):
    fw = firmware.find_firmware(extra_dirs=[str(tmp_path)])
    assert fw.found is False
    assert fw.bootrom is None
    assert fw.fullimage is None
    assert str(tmp_path) in fw.searched


def test_find_firmware_detects_elf(tmp_path):
    (tmp_path / "bootrom.elf").write_bytes(b"\x7fELF")
    (tmp_path / "fullimage.elf").write_bytes(b"\x7fELF")
    fw = firmware.find_firmware(extra_dirs=[str(tmp_path)])
    assert fw.found is True
    assert fw.bootrom == os.path.join(str(tmp_path), "bootrom.elf")
    assert fw.fullimage == os.path.join(str(tmp_path), "fullimage.elf")
