"""Test penampil dump — memakai dump sintetis di memori/temp file."""

import json

from pm3tool import dumpview


def _make_1k() -> bytes:
    data = bytearray(1024)
    # blok 4 (sektor 1) berisi teks ASCII
    text = b"Hello World\x00\x00\x00\x00\x00"
    data[4 * 16:4 * 16 + 16] = text
    # trailer sektor 1 = blok 7
    trailer = bytes.fromhex("A0A1A2A3A4A5" + "FF0780" + "69" + "B0B1B2B3B4B5")
    data[7 * 16:7 * 16 + 16] = trailer
    return bytes(data)


def test_sector_layout_1k():
    layout = dumpview.sector_layout(1024)
    assert len(layout) == 16
    assert layout[0] == (0, [0, 1, 2, 3])
    assert layout[1] == (1, [4, 5, 6, 7])


def test_sector_layout_4k():
    layout = dumpview.sector_layout(4096)
    assert len(layout) == 40            # 32 kecil + 8 besar
    assert layout[32][1][:2] == [128, 129]
    assert len(layout[32][1]) == 16


def test_parse_sectors_arg():
    assert dumpview.parse_sectors_arg("1-4", 15) == {1, 2, 3, 4}
    assert dumpview.parse_sectors_arg("1,3,5", 15) == {1, 3, 5}
    assert dumpview.parse_sectors_arg("1-2,7", 15) == {1, 2, 7}
    assert dumpview.parse_sectors_arg("", 15) is None
    assert dumpview.parse_sectors_arg("99", 15) == set()  # di luar batas


def test_format_ascii_shows_text():
    data = _make_1k()
    out = dumpview.format_dump(data, sectors={1}, mode="ascii")
    assert "Hello World" in out


def test_format_both_has_hex_and_ascii():
    data = _make_1k()
    out = dumpview.format_dump(data, sectors={1}, mode="both")
    assert "48 65 6C 6C 6F" in out          # 'Hello' hex
    assert "|Hello World" in out
    assert "KeyA=A0A1A2A3A4A5" in out        # trailer terbaca


def test_filter_only_requested_sector():
    out = dumpview.format_dump(_make_1k(), sectors={1}, mode="both")
    assert "Sector 1" in out
    assert "Sector 2" not in out


def test_load_bin_eml_json_equivalent(tmp_path):
    data = _make_1k()
    binp = tmp_path / "d.bin"
    binp.write_bytes(data)
    # .eml: satu baris hex per blok
    eml = "\n".join(data[i:i + 16].hex() for i in range(0, len(data), 16))
    emlp = tmp_path / "d.eml"
    emlp.write_text(eml)
    # .json gaya Iceman
    blocks = {str(i // 16): data[i:i + 16].hex() for i in range(0, len(data), 16)}
    jsonp = tmp_path / "d.json"
    jsonp.write_text(json.dumps({"blocks": blocks}))

    assert dumpview.load_dump(str(binp)) == data
    assert dumpview.load_dump(str(emlp)) == data
    assert dumpview.load_dump(str(jsonp)) == data
