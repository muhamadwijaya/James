"""Simulasi autentikasi nyata: Key A tersembunyi, data/key diverifikasi ulang."""

import hashlib
import json
import re
import shlex
import threading
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from pm3tool import ink
from pm3tool.client import PM3Result


def blank(uid="11223344"):
    data = bytearray(1024)
    first = bytes.fromhex(uid)
    data[:4] = first
    data[4] = first[0] ^ first[1] ^ first[2] ^ first[3]
    data[5:16] = bytes.fromhex("08 04 00 05 00 00 00 00 00 00 90")
    for sector in range(16):
        data[(sector * 4 + 3) * 16:(sector * 4 + 4) * 16] = bytes.fromhex("FFFFFFFFFFFFFF078069FFFFFFFFFFFF")
    return bytes(data)


class Chip:
    port = "COM11"

    def __init__(self, data=None, magic=False, fail_block=None, corrupt_key_b=False, final_corrupt=False):
        self.data = bytearray(data if data is not None else blank())
        self.magic = magic
        self.fail_block = fail_block
        self.corrupt_key_b = corrupt_key_b
        self.final_corrupt = final_corrupt
        self.calls = []
        self.writes = []

    def run(self, command, timeout=None):
        self.calls.append(command)
        argv = shlex.split(command)
        rc = 0
        if command == "hf 14a info":
            output = f"[+] UID: {self.data[:4].hex().upper()}\n[+] SAK: 08 [2]\n"
        elif argv[:3] == ["hf", "mf", "dump"]:
            keydata = Path(argv[argv.index('-k') + 1]).read_bytes()
            assert len(keydata) == 192
            for sector in range(16):
                trailer = (sector * 4 + 3) * 16
                assert keydata[sector*6:(sector+1)*6] == self.data[trailer:trailer+6], "Dump must authenticate with the current Key A"
            value = bytearray(self.data)
            if self.final_corrupt and self.writes:
                value[20 * 16] ^= 1
            Path(argv[argv.index('-f') + 1] + '.bin').write_bytes(value)
            output = "[+] Succeeded in dumping all blocks\n"
        elif argv[:3] in (["hf", "mf", "rdbl"], ["hf", "mf", "cgetblk"]):
            block = int(argv[argv.index('--blk') + 1])
            if argv[2] == 'cgetblk' and not self.magic:
                return PM3Result(command, "[!] Can't read block", "", 1)
            value = bytes(self.data[block*16:(block+1)*16])
            if argv[2] == 'rdbl':
                key = bytes.fromhex(argv[argv.index('-k') + 1])
                trailer = (block // 4 * 4 + 3) * 16
                assert '-a' in argv
                assert key == self.data[trailer:trailer+6], "rdbl must authenticate with the current Key A"
                if block % 4 == 3:
                    value = bytes(6) + value[6:]  # Physical Key A cannot be read.
            output = f"[=] {block // 4} | {block} | {value.hex(' ').upper()} | ................\n"
        elif argv[:3] in (["hf", "mf", "wrbl"], ["hf", "mf", "csetblk"]):
            block = int(argv[argv.index('--blk') + 1])
            if argv[2] == 'wrbl':
                assert block != 0
                trailer = (block // 4 * 4 + 3) * 16
                assert bytes.fromhex(argv[argv.index('-k') + 1]) == self.data[trailer:trailer+6]
            else:
                assert self.magic
                assert '-w' not in argv  # No implicit wipe.
            if block == self.fail_block:
                output = "[!] Write ( fail )\n"
            else:
                self.data[block*16:(block+1)*16] = bytes.fromhex(argv[argv.index('-d') + 1])
                self.writes.append(block)
                if self.corrupt_key_b and block % 4 == 3:
                    self.data[block*16+10] ^= 1
                output = "[+] Write ( ok )\n" if argv[2] == 'wrbl' else f"[=] Writing block number {block}\n"
        else:
            raise AssertionError(command)
        return PM3Result(command, output, "", rc)


@pytest.mark.parametrize('uid,sha,block6', [
    ('C2A4DA95', '9373f5574774534be530b0234106dec0c647062872d447e2f790453d3e901a69', '30E8030100000000000000000000001D'),
    ('D2E2DC95', 'b9b31c8bfc2b4258fe1b81315a83dbec85286752239c7d4a517adcfd21773fe1', '00E8030100000000000000000000004D'),
])
def test_presets_match_supplied_dump(uid, sha, block6):
    source = ink.reference(uid)
    assert len(source.data) == 1024 and source.sha256 == sha
    assert source.uid == uid and source.product == 'BKA236T'
    assert source.data[64:80].hex().upper() == '424B4132333654010000000000001A03'
    assert source.data[80:96].hex().upper() == '15323630333231210700000040420F00'
    assert source.data[96:112].hex().upper() == block6
    for block in range(64):
        raw = source.data[block*16:(block+1)*16]
        if block % 4 == 3:
            key = bytes.fromhex('436F44506144' if block // 4 in (1,3,4) else 'FFFFFFFFFFFF')
            assert raw == key + bytes.fromhex('FF078069') + key
        elif block not in (0,4,5,6,12,13,16,17):
            assert raw == bytes(16)
    packaged_key = Path(ink.__file__).parent / 'ink_references' / f'hf-mf-{uid}-unused-key.bin'
    assert packaged_key.read_bytes() == ink.keyfile(source.data)


@pytest.mark.parametrize('mode', ['normal', 'gen1a'])
@pytest.mark.parametrize('uid', ['C2A4DA95', 'D2E2DC95'])
def test_write_blank_chip_copies_all_data_and_keys(tmp_path, mode, uid):
    source = ink.reference(uid)
    client = Chip(magic=mode == 'gen1a')
    original = bytes(client.data)
    plan = ink.prepare(client, source, mode, str(tmp_path))
    assert not client.writes
    session = Path(plan.session_dir)
    assert (session/'before.bin').read_bytes() == original
    assert (session/'reference-key.bin').read_bytes() == ink.keyfile(source.data)
    report = ink.execute(client, plan)
    expected = source.data if mode == 'gen1a' else original[:16] + source.data[16:]
    assert report.verified and bytes(client.data) == expected
    assert report.uid == (uid if mode == 'gen1a' else '11223344')
    assert report.exact_with_uid == (mode == 'gen1a')
    assert (session/'after.bin').read_bytes() == expected
    assert report.written_blocks == tuple(client.writes)
    for sector in range(16):
        trailer = sector * 4 + 3
        if trailer in client.writes:
            for block in range(sector*4, trailer):
                if block and block in client.writes:
                    assert client.writes.index(block) < client.writes.index(trailer)
    if mode == 'gen1a':
        assert client.writes[-1] == 0
    else:
        assert 0 not in client.writes
        assert any('-k 436F44506144' in c for c in client.calls if c.startswith('hf mf rdbl --blk 7 '))
    journal = json.loads((session/'journal.json').read_text())
    assert journal['status'] == 'verified'
    assert journal['matched_blocks'] == (64 if mode == 'gen1a' else 63)
    assert journal['actual_sha256'] == hashlib.sha256(expected).hexdigest()
    with pytest.raises(ink.InkError, match='sudah digunakan'):
        ink.execute(client, plan)


@pytest.mark.parametrize('block', [1,4,8,56,62])
def test_nonempty_target_rejected_before_write(tmp_path, block):
    data = bytearray(blank())
    data[block*16] = 1
    client = Chip(data)
    with pytest.raises(ink.InkError, match='tidak kosong'):
        ink.prepare(client, ink.reference('C2A4DA95'), output_dir=str(tmp_path))
    assert not client.writes


def test_gen1a_rejected_on_regular_chip(tmp_path):
    client = Chip()
    with pytest.raises(ink.InkError, match='Gen1a'):
        ink.prepare(client, ink.reference('C2A4DA95'), 'gen1a', str(tmp_path))
    assert not client.writes


@pytest.mark.parametrize('mutation,expected', [('uid', 'Chip berubah'), ('data', 'berubah sejak preview')])
def test_changed_target_between_preview_and_write(tmp_path, mutation, expected):
    client = Chip()
    plan = ink.prepare(client, ink.reference('C2A4DA95'), output_dir=str(tmp_path))
    if mutation == 'uid':
        client.data[0] ^= 1
        client.data[4] ^= 1
    else:
        client.data[4*16] = 1
    with pytest.raises(ink.InkError, match=expected):
        ink.execute(client, plan)
    assert not client.writes
    assert json.loads((Path(plan.session_dir)/'journal.json').read_text())['status'] == 'aborted_before_write'


def test_failed_write_retains_partial_journal_and_original_keys(tmp_path):
    client = Chip(fail_block=12)
    plan = ink.prepare(client, ink.reference('C2A4DA95'), output_dir=str(tmp_path))
    with pytest.raises(ink.InkError, match='blok 12'):
        ink.execute(client, plan)
    session = Path(plan.session_dir)
    journal = json.loads((session/'journal.json').read_text())
    assert journal['status'] == 'incomplete' and journal['pending_block'] == 12
    assert journal['written_blocks'] == [4,5,6,7]
    assert (session/'before-key.bin').read_bytes() == bytes.fromhex('FFFFFFFFFFFF')*32
    assert (session/'before.bin').read_bytes() == blank()
    assert bytes(client.data[7*16:8*16]) == plan.reference.data[7*16:8*16]


@pytest.mark.parametrize('defect', ['key_b','final'])
def test_readback_mismatch_never_reported_success(tmp_path, defect):
    client = Chip(corrupt_key_b=defect == 'key_b', final_corrupt=defect == 'final')
    plan = ink.prepare(client, ink.reference('C2A4DA95'), output_dir=str(tmp_path))
    with pytest.raises(ink.InkError, match='tidak cocok'):
        ink.execute(client, plan)
    journal = json.loads((Path(plan.session_dir)/'journal.json').read_text())
    assert journal['status'] == 'incomplete'


def test_cancel_after_first_verified_block(tmp_path):
    client = Chip()
    event = threading.Event()
    plan = ink.prepare(client, ink.reference('C2A4DA95'), output_dir=str(tmp_path))
    def emit(text):
        if text.startswith('Blok 4:'):
            event.set()
    with pytest.raises(ink.InkError, match='dihentikan'):
        ink.execute(client, plan, emit, event)
    assert client.writes == [4]


def test_tampered_plan_cannot_write(tmp_path):
    client = Chip()
    plan = ink.prepare(client, ink.reference('C2A4DA95'), output_dir=str(tmp_path))
    with pytest.raises(ink.InkError, match='tidak cocok'):
        ink.execute(client, replace(plan, after=blank()))
    assert not client.writes


def test_invalid_acl_reference_or_nontransport_target(tmp_path):
    source = ink.reference('C2A4DA95')
    data = bytearray(source.data)
    data[7*16+6:7*16+9] = bytes.fromhex('7F0788')
    filename = tmp_path/'unsupported.bin'
    filename.write_bytes(data)
    with pytest.raises(ink.InkError, match='ACL acuan sektor 1'):
        ink.reference(str(filename))
    target = bytearray(blank())
    target[3*16+6:3*16+9] = bytes.fromhex('7F0788')
    client = Chip(target)
    with pytest.raises(ink.InkError, match='ACL transport'):
        ink.prepare(client, source, output_dir=str(tmp_path))
    assert not client.writes


def test_external_source_and_export_preserve_distinct_a_b_keys(tmp_path):
    raw = bytearray(ink.reference('C2A4DA95').data)
    raw[7*16+10:8*16] = bytes.fromhex('112233445566')
    sourcefile = tmp_path/'custom.bin'
    sourcefile.write_bytes(raw)
    source = ink.reference(str(sourcefile))
    client = Chip()
    plan = ink.prepare(client, source, output_dir=str(tmp_path))
    report = ink.execute(client, plan)
    assert report.verified and bytes(client.data[16:]) == bytes(raw[16:])
    dump, keys = ink.export_reference(source, str(tmp_path/'export.bin'))
    assert Path(dump).read_bytes() == raw
    assert Path(keys).read_bytes() == ink.keyfile(raw)
    with pytest.raises(ink.InkError, match='File sudah ada'):
        ink.export_reference(source, dump)


@pytest.mark.parametrize('uid', ['C2A4DA95', 'D2E2DC95'])
def test_custom_code_and_date_write_known_fields_only(uid):
    source = ink.reference(uid)
    assert ink.read_fields(source) == ink.InkFields('BKA236T', date(2026, 3, 21))
    assert ink.customize_reference(source, 'BKA236T', date(2026, 3, 21)) is source
    custom = ink.customize_reference(source, 'BK999T', date(2028, 2, 29))
    assert custom.data[64:72] == b'BK999T\x00\x01'
    assert custom.data[78:89] == bytes.fromhex('1C021D') + b'280229' + bytes.fromhex('2107')
    assert ink.read_fields(custom) == ink.InkFields('BK999T', date(2028, 2, 29))
    allowed = set(range(64,71)) | set(range(78,87))
    assert all(a == b for i,(a,b) in enumerate(zip(source.data, custom.data)) if i not in allowed)
    assert custom.data[96:112] == source.data[96:112]  # Unknown block 6 checksum preserved.
    assert custom.data[192:320] == source.data[192:320]  # Full sectors 3/4 unchanged.
    assert custom.data[128:176] == bytes(48)  # Empty sector 2 remains empty.
    assert ink.keyfile(custom.data) == ink.keyfile(source.data)
    assert source.sha256 == hashlib.sha256(source.data).hexdigest()
    assert custom.sha256 == hashlib.sha256(custom.data).hexdigest() != source.sha256
    assert custom.customization.metadata()['printer_compatibility'] == 'not_verified'


@pytest.mark.parametrize('chosen', [date(2000,1,1),date(2028,2,29),date(2099,12,31)])
def test_custom_dates_keep_ascii_and_binary_consistent(chosen):
    source = ink.reference('C2A4DA95')
    custom = ink.customize_reference(source, source.product, chosen)
    assert custom.data[78:81] == bytes((chosen.year-2000, chosen.month, chosen.day))
    assert custom.data[81:87] == chosen.strftime('%y%m%d').encode('ascii')
    assert ink.read_fields(custom).record_date == chosen


@pytest.mark.parametrize('product', ['', 'BKA236T1', 'bka236t', 'BK A', 'BKé', 'BK\n'])
def test_invalid_custom_code_is_rejected(product):
    with pytest.raises(ink.InkError, match='Kode BK'):
        ink.customize_reference(ink.reference('C2A4DA95'), product, date(2026,10,10))


@pytest.mark.parametrize('chosen', [date(1999,12,31),date(2100,1,1),'2026-10-10',None])
def test_unsupported_custom_date_is_rejected(chosen):
    with pytest.raises(ink.InkError, match='Tanggal harus valid'):
        ink.customize_reference(ink.reference('C2A4DA95'), 'BKA236T', chosen)


def test_customization_only_updates_sector2_if_it_is_a_mirror(tmp_path):
    source = ink.reference('C2A4DA95')
    raw = bytearray(source.data)
    raw[128:192] = raw[64:128]
    path = tmp_path/'mirrored.bin'
    path.write_bytes(raw)
    mirrored = ink.reference(str(path))
    custom = ink.customize_reference(mirrored, 'BKA777T', date(2027,11,30))
    assert custom.data[128:176] == custom.data[64:112]
    assert custom.data[176:192] == mirrored.data[176:192]
    assert custom.customization.field_blocks == (4,5,8,9)
    raw[128] ^= 1
    path.write_bytes(raw)
    separate = ink.reference(str(path))
    custom = ink.customize_reference(separate, 'BKA777T', date(2027,11,30))
    assert custom.data[128:192] == separate.data[128:192]


@pytest.mark.parametrize('offset,value,expected', [(81,ord('9'),'tidak cocok'),(79,13,'tidak valid'),(71,0,'belum didukung')])
def test_inconsistent_or_unknown_date_layout_cannot_be_customized(tmp_path, offset, value, expected):
    raw = bytearray(ink.reference('C2A4DA95').data)
    raw[offset] = value
    path = tmp_path/'unsupported-date.bin'
    path.write_bytes(raw)
    source = ink.reference(str(path))  # Exact copy still supports this full dump.
    with pytest.raises(ink.InkError, match=expected):
        ink.customize_reference(source, 'BKA236T', date(2027,1,1))


@pytest.mark.parametrize('mode', ['normal', 'gen1a'])
def test_customized_write_export_and_journal_use_requested_values(tmp_path, mode):
    original = ink.reference('D2E2DC95')
    custom = ink.customize_reference(original, 'BKA999T', date(2027,11,30))
    client = Chip(magic=mode == 'gen1a')
    initial = bytes(client.data)
    logs = []
    plan = ink.prepare(client, custom, mode, str(tmp_path), logs.append)
    preview = json.loads((Path(plan.session_dir)/'preview.json').read_text())
    assert preview['customization']['source_sha256'] == original.sha256
    assert preview['customization']['date_ascii'] == '271130'
    assert preview['customization']['original_date'] == '2026-03-21'
    assert preview['customization']['product'] == 'BKA999T'
    assert any('BKA999T' in text and '30/11/2027' in text for text in logs)
    report = ink.execute(client, plan)
    expected = custom.data if mode == 'gen1a' else initial[:16]+custom.data[16:]
    assert report.verified and bytes(client.data) == expected
    assert client.data[64:71] == b'BKA999T'
    assert client.data[78:87] == bytes.fromhex('1B0B1E')+b'271130'
    journal = json.loads((Path(plan.session_dir)/'journal.json').read_text())
    assert journal['customization'] == preview['customization']
    assert journal['printer_compatibility'] == 'not_verified'
    output, keys = ink.export_reference(custom, str(tmp_path/'custom.bin'))
    assert Path(output).read_bytes() == custom.data
    assert Path(keys).read_bytes() == ink.keyfile(original.data)
