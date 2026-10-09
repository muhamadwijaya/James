"""Test parser output PM3 — tidak butuh perangkat keras."""

from pm3tool import parse


HF_SAMPLE = """
[usb] pm3 --> hf 14a info
[+]  UID: 04 A2 B3 C4 D5 E6 F0
[+] ATQA: 00 44
[+]  SAK: 00 [2]
"""

LF_SAMPLE = """
[usb] pm3 --> lf search
[+] EM 410x ID 1234567890
[+] Valid EM410x ID found!
"""

AUTOPWN_SAMPLE = """
[+] found keys:
[+]  0 | A | FFFFFFFFFFFF | 1
[+]  0 | B | A0A1A2A3A4A5 | 1
[+]  1 | A | D3F7D3F7D3F7 | 0
"""


def test_parse_uid():
    assert parse.parse_uid(HF_SAMPLE) == "04A2B3C4D5E6F0"


def test_parse_hf_identity():
    ident = parse.parse_hf_identity(HF_SAMPLE)
    assert ident["uid"] == "04A2B3C4D5E6F0"
    assert ident["atqa"] == "0044"
    assert ident["sak"] == "00"


def test_parse_lf_em410x():
    assert parse.parse_lf_em410x(LF_SAMPLE) == "1234567890"


def test_parse_found_keys():
    keys = parse.parse_found_keys(AUTOPWN_SAMPLE)
    assert len(keys) == 3
    assert keys[0] == {"sector": "0", "type": "A", "key": "FFFFFFFFFFFF"}
    assert keys[1]["key"] == "A0A1A2A3A4A5"
    assert keys[2]["type"] == "A"


def test_parse_no_match_returns_none():
    assert parse.parse_uid("tidak ada apa-apa") is None
    assert parse.parse_lf_em410x("kosong") is None
    assert parse.parse_found_keys("kosong") == []
