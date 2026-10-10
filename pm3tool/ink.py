"""Isi chip ink baru dari acuan, dengan kode/tanggal Codpad yang dapat diisi.

Mode biasa menyalin blok 1–63 termasuk trailer. Mode Gen1a juga menyalin
blok 0. Hanya kartu 1K yang data normalnya kosong dan key/ACL transport
yang diterima. Key baru ditulis setelah seluruh data sektor terverifikasi.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import dumpview, parse, recycle

PRESETS = (
    ("C2A4DA95", "BKA236T — C2A4DA95 — belum terpakai"),
    ("D2E2DC95", "BKA236T — D2E2DC95 — belum terpakai"),
)
MODES = {"normal": "Chip biasa — data dan key; UID chip baru",
         "gen1a": "Magic Gen1a — seluruh dump termasuk UID"}
DEFAULT_KEY = "FFFFFFFFFFFF"
TRANSPORT_ACL = bytes.fromhex("FF0780")


class InkError(RuntimeError):
    pass


@dataclass(frozen=True)
class InkFields:
    product: str
    record_date: date


@dataclass(frozen=True)
class InkCustomization:
    source_sha256: str
    original_product: str
    original_date: date
    product: str
    record_date: date
    field_blocks: tuple[int, ...]

    def metadata(self):
        return {"source_sha256": self.source_sha256,
                "original_product": self.original_product,
                "original_date": self.original_date.isoformat(),
                "product": self.product, "date": self.record_date.isoformat(),
                "date_ascii": self.record_date.strftime("%y%m%d"),
                "field_blocks": list(self.field_blocks),
                "unknown_validation_fields": "preserved_from_reference",
                "printer_compatibility": "not_verified"}


@dataclass(frozen=True)
class InkReference:
    name: str
    data: bytes = field(repr=False)
    sha256: str
    customization: InkCustomization | None = None

    @property
    def uid(self):
        return self.data[:4].hex().upper()

    @property
    def product(self):
        raw = self.data[64:71].split(b"\x00", 1)[0]
        return "".join(chr(v) for v in raw if 32 <= v <= 126)

    @property
    def text(self):
        return "".join(chr(v) for v in self.data[80:96] if 32 <= v <= 126)


@dataclass(frozen=True)
class InkPlan:
    reference: InkReference
    mode: str
    uid: str
    before: bytes = field(repr=False)
    after: bytes = field(repr=False)
    session_dir: str
    changes: tuple[recycle.BlockChange, ...]


@dataclass(frozen=True)
class InkReport:
    uid: str
    session_dir: str
    verified: bool
    written_blocks: tuple[int, ...]
    exact_with_uid: bool


def keyfile(data: bytes) -> bytes:
    return b"".join(data[(s * 4 + 3) * 16 + offset:(s * 4 + 3) * 16 + offset + 6]
                    for offset in (0, 10) for s in range(16))


def _validate_reference(data: bytes):
    if len(data) != 1024 or data[4] != data[0] ^ data[1] ^ data[2] ^ data[3] or data[5] != 8:
        raise InkError("Acuan harus dump MIFARE 1K lengkap dengan UID 4 byte/BCC yang valid.")
    # Pembacaan balik trailer dan perubahan key didukung pada ACL transport.
    for sector in range(16):
        trailer = data[(sector * 4 + 3) * 16:(sector * 4 + 4) * 16]
        if trailer[6:9] != TRANSPORT_ACL:
            raise InkError(f"ACL acuan sektor {sector} belum didukung. Gunakan acuan FF0780 seperti contoh ink.")


def reference(selection: str) -> InkReference:
    if selection in dict(PRESETS):
        path = Path(__file__).parent / "ink_references" / f"hf-mf-{selection}-unused.bin"
        name = dict(PRESETS)[selection]
    else:
        path = Path(selection).expanduser().resolve()
        name = path.name
    data = recycle._load_dump(str(path))
    _validate_reference(data)
    return InkReference(name, data, hashlib.sha256(data).hexdigest())


def _check_reference(source: InkReference):
    _validate_reference(source.data)
    if hashlib.sha256(source.data).hexdigest() != source.sha256:
        raise InkError("Data acuan berubah sejak dimuat.")


def read_fields(source: InkReference) -> InkFields:
    """Baca format kode/tanggal yang cocok dengan dump keluarga CoDPaD.

    Jenis tanggal (produksi/kedaluwarsa/dll.) belum diketahui. Kedua
    representasi tanggal wajib konsisten sebelum personalisasi diizinkan.
    """
    _check_reference(source)
    product = source.data[64:71].rstrip(b"\x00")
    ascii_date = source.data[81:87]
    if (not re.fullmatch(rb"[A-Z0-9]{1,7}", product)
            or source.data[64:71] != product.ljust(7, b"\x00")
            or source.data[71] not in (1, 2)
            or source.data[87:89] != bytes.fromhex("2107")
            or source.data[112:118] != bytes.fromhex("436F44506144")
            or not re.fullmatch(rb"[0-9]{6}", ascii_date)
            or source.data[78] > 99):
        raise InkError("Format kode BK/tanggal acuan belum didukung untuk personalisasi.")
    try:
        record_date = date(2000 + source.data[78], source.data[79], source.data[80])
    except ValueError as exc:
        raise InkError("Tanggal biner pada acuan tidak valid.") from exc
    if ascii_date != record_date.strftime("%y%m%d").encode("ascii"):
        raise InkError("Tanggal ASCII dan tanggal biner acuan tidak cocok.")
    return InkFields(product.decode("ascii"), record_date)


def customize_reference(source: InkReference, product: str, record_date: date) -> InkReference:
    """Ubah hanya kode dan dua bentuk tanggal; tidak menebak CRC/MAC.

    Sektor 2 disinkronkan hanya jika sudah merupakan salinan lengkap data
    sektor 1 pada acuan. Sektor 2 kosong tetap kosong. Key tidak berubah.
    """
    original = read_fields(source)
    if not isinstance(product, str) or not re.fullmatch(r"[A-Z0-9]{1,7}", product):
        raise InkError("Kode BK harus 1–7 huruf kapital A–Z atau angka 0–9, misalnya BKA236T.")
    if (not isinstance(record_date, date) or isinstance(record_date, datetime)
            or not 2000 <= record_date.year <= 2099):
        raise InkError("Tanggal harus valid dan berada pada tahun 2000–2099.")
    if product == original.product and record_date == original.record_date:
        return source
    data = bytearray(source.data)
    data[64:71] = product.encode("ascii").ljust(7, b"\x00")
    data[78:81] = bytes((record_date.year - 2000, record_date.month, record_date.day))
    data[81:87] = record_date.strftime("%y%m%d").encode("ascii")
    blocks = (4, 5)
    if source.data[128:176] == source.data[64:112]:
        data[128:160] = data[64:96]
        blocks += (8, 9)
    result = bytes(data)
    modification = InkCustomization(source.sha256, original.product, original.record_date,
                                    product, record_date, blocks)
    return InkReference(f"{source.name} — {product} — {record_date:%d/%m/%Y}", result,
                        hashlib.sha256(result).hexdigest(), modification)


def _check_blank(data: bytes):
    if len(data) != 1024 or data[5] != 8 or data[4] != data[0] ^ data[1] ^ data[2] ^ data[3]:
        raise InkError("Target harus chip MIFARE Classic 1K dengan SAK 08.")
    for block in range(1, 64):
        raw = data[block * 16:(block + 1) * 16]
        if block % 4 != 3:
            if raw != bytes(16):
                raise InkError(f"Target tidak kosong: blok {block} berisi data. Gunakan chip baru kosong.")
        elif raw[:6] != bytes.fromhex(DEFAULT_KEY) or raw[10:] != bytes.fromhex(DEFAULT_KEY) or raw[6:9] != TRANSPORT_ACL:
            raise InkError(f"Target sektor {block // 4} belum menggunakan key FFFFFFFFFFFF dan ACL transport.")


def _check_cancel(cancel):
    if cancel and cancel.is_set():
        raise InkError("Penulisan dihentikan. Lihat journal untuk blok yang sudah ditulis.")


def _identity(client, expected=None):
    result = client.run("hf 14a info", timeout=30)
    identity = parse.parse_hf_identity(recycle._text(result))
    uid = identity["uid"]
    if not result.ok or not uid or len(uid) != 8 or identity["sak"] != "08":
        raise InkError("Chip 1K dengan UID 4 byte/SAK 08 belum terbaca. Tempelkan chip kosong pada antena.")
    if expected and uid != expected:
        raise InkError(f"Chip berubah: UID {uid}, target preview {expected}.")
    return uid


def _magic_read(client, block):
    result = client.run(f"hf mf cgetblk --blk {block}", timeout=30)
    if result.ok:
        for line in recycle._text(result).splitlines():
            parts = line.split("|")
            for i in range(1, len(parts)):
                number = re.sub(r"^\s*\[[^]]+\]\s*", "", parts[i - 1]).strip()
                if number.isdecimal() and int(number) == block and re.fullmatch(
                        r"(?:[0-9a-f]{2}\s+){15}[0-9a-f]{2}", parts[i].strip(), re.I):
                    return bytes.fromhex(parts[i])
    raise InkError(f"Blok {block} tidak dapat dibaca lewat Gen1a. Periksa jenis chip/mode yang dipilih.")


def _snapshot(client, mode, keypath, stem, cancel=None):
    if mode == "normal":
        _check_cancel(cancel)
        return recycle._dump(client, keypath, stem)
    chunks = []
    for block in range(64):
        _check_cancel(cancel)
        chunks.append(_magic_read(client, block))
    data = b"".join(chunks)
    stem.with_suffix(".bin").write_bytes(data)
    return data


def prepare(client, source: InkReference, mode="normal", output_dir="ink_writes",
            emit=None, cancel: threading.Event | None = None) -> InkPlan:
    """Preview live: baca chip kosong dan backup, belum menulis satu blok pun."""
    _check_reference(source)
    if mode not in MODES:
        raise InkError("Mode penulisan tidak valid.")
    _check_cancel(cancel)
    uid = _identity(client)
    session = Path(output_dir).expanduser().resolve() / (
        uid + "_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8])
    recycle._quoted_path(session)
    session.mkdir(parents=True)
    keys = session / "before-key.bin"
    keys.write_bytes(bytes.fromhex(DEFAULT_KEY) * 32)
    (session / "reference.bin").write_bytes(source.data)
    (session / "reference-key.bin").write_bytes(keyfile(source.data))
    if emit:
        emit(f"Membaca dan membackup chip baru UID {uid}…\n")
    before = _snapshot(client, mode, keys, session / "before", cancel)
    _identity(client, uid)
    _check_blank(before)
    if before[:4].hex().upper() != uid:
        raise InkError("UID backup tidak cocok dengan chip yang sedang ditempelkan.")
    after = source.data if mode == "gen1a" else before[:16] + source.data[16:]
    (session / "expected.bin").write_bytes(after)
    changes = tuple(recycle.BlockChange(i, before[i * 16:(i + 1) * 16], after[i * 16:(i + 1) * 16])
                    for i in range(64) if before[i * 16:(i + 1) * 16] != after[i * 16:(i + 1) * 16])
    metadata = {"status": "prepared", "uid_before": uid, "uid_after": after[:4].hex().upper(),
                "mode": mode, "reference": source.name, "reference_sha256": source.sha256,
                "before_sha256": hashlib.sha256(before).hexdigest(),
                "expected_sha256": hashlib.sha256(after).hexdigest(),
                "blocks": [c.block for c in changes],
                "customization": source.customization.metadata() if source.customization else None,
                "printer_compatibility": "not_verified"}
    (session / "preview.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    if emit:
        emit(f"Chip kosong terkonfirmasi. {len(changes)} blok berubah; data dan key mengikuti acuan.\n")
        if source.customization:
            emit(f"Kode BK: {source.customization.product}; tanggal: {source.customization.record_date:%d/%m/%Y} "
                 f"(ASCII {source.customization.record_date:%y%m%d}, biner YY/MM/DD). "
                 "Field validasi lain mengikuti acuan; penerimaan printer belum diuji.\n")
    return InkPlan(source, mode, uid, before, after, str(session), changes)


def execute(client, plan: InkPlan, emit=None, cancel: threading.Event | None = None) -> InkReport:
    """Data per sektor dahulu, trailer/key terakhir, blok 0 paling akhir."""
    _check_reference(plan.reference)
    _check_blank(plan.before)
    expected = plan.reference.data if plan.mode == "gen1a" else plan.before[:16] + plan.reference.data[16:]
    if plan.mode not in MODES or plan.after != expected or plan.uid != plan.before[:4].hex().upper():
        raise InkError("Rencana penulisan tidak cocok dengan acuan/target.")
    changes = tuple(recycle.BlockChange(i, plan.before[i * 16:(i + 1) * 16], plan.after[i * 16:(i + 1) * 16])
                    for i in range(64) if plan.before[i * 16:(i + 1) * 16] != plan.after[i * 16:(i + 1) * 16])
    if plan.changes != changes:
        raise InkError("Daftar perubahan pada preview tidak valid.")
    session = Path(plan.session_dir)
    # Sekali preview untuk sekali eksekusi. Sesi gagal juga tidak ditulis ulang.
    try:
        with (session / "write-started").open("x", encoding="utf-8") as handle:
            handle.write(plan.reference.sha256)
    except FileExistsError as exc:
        raise InkError("Preview sudah digunakan. Buat preview baru pada chip kosong.") from exc
    written = []
    journal = {"status": "preflight", "uid_before": plan.uid, "uid_after": plan.after[:4].hex().upper(),
               "mode": plan.mode, "reference_sha256": plan.reference.sha256,
               "customization": plan.reference.customization.metadata() if plan.reference.customization else None,
               "printer_compatibility": "not_verified",
               "written_blocks": written, "pending_block": None}

    def record():
        temporary = session / "journal.tmp"
        temporary.write_text(json.dumps(journal, indent=2), encoding="utf-8")
        temporary.replace(session / "journal.json")

    def log(message):
        with (session / "session.log").open("a", encoding="utf-8") as handle:
            handle.write(message + "\n")
        if emit:
            emit(message + "\n")

    record()
    current_uid = plan.uid
    try:
        _check_cancel(cancel)
        _identity(client, current_uid)
        baseline = _snapshot(client, plan.mode, session / "before-key.bin", session / "preflight", cancel)
        if baseline != plan.before:
            raise InkError("Chip berubah sejak preview. Baca ulang chip kosong sebelum menulis.")
        _check_blank(baseline)
        journal["status"] = "writing"
        record()
        changed = {c.block: c for c in plan.changes}
        ordered = [i for i in range(1, 64) if i in changed]
        if 0 in changed:
            ordered.append(0)
        for block in ordered:
            _check_cancel(cancel)
            _identity(client, current_uid)
            change = changed[block]
            key = DEFAULT_KEY
            if plan.mode == "normal":
                original = recycle._read_block(client, block, key, "A")
                if block % 4 == 3:
                    original = bytes.fromhex(key) + original[6:]
                if original != change.before:
                    raise InkError(f"Blok {block} berubah sebelum ditulis.")
                command = f"hf mf wrbl --blk {block} -a -k {key} -d {change.after.hex().upper()}"
            else:
                if _magic_read(client, block) != change.before:
                    raise InkError(f"Blok {block} berubah sebelum ditulis.")
                command = f"hf mf csetblk --blk {block} -d {change.after.hex().upper()}"
            journal["pending_block"] = block
            record()
            result = client.run(command, timeout=30)
            raw = recycle._text(result)
            if not result.ok or re.search(r"\b(fail|failed|error|unknown command|can't write)\b", raw, re.I) or (
                    plan.mode == "normal" and not re.search(r"\bWrite\s*\(\s*ok\s*\)", raw, re.I)):
                raise InkError(f"Penulisan blok {block} belum berhasil: {raw.strip()}")
            if block == 0:
                current_uid = plan.after[:4].hex().upper()
            _identity(client, current_uid)
            if plan.mode == "normal":
                verify_key = change.after[:6].hex().upper() if block % 4 == 3 else key
                actual = recycle._read_block(client, block, verify_key, "A")
                # Key A tidak dapat dibaca; autentikasi dengan key baru membuktikannya.
                if block % 4 == 3:
                    actual = change.after[:6] + actual[6:]
            else:
                actual = _magic_read(client, block)
            if actual != change.after:
                raise InkError(f"Verifikasi blok {block} tidak cocok dengan acuan.")
            written.append(block)
            journal["pending_block"] = None
            record()
            log(f"Blok {block}: data/key ditulis dan dibaca ulang, cocok ({len(written)}/{len(ordered)}).")
        _check_cancel(cancel)
        _identity(client, current_uid)
        final = _snapshot(client, plan.mode, session / "reference-key.bin", session / "after", cancel)
        if final != plan.after:
            raise InkError("Dump akhir tidak cocok dengan acuan dan pilihan UID.")
        journal["status"] = "verified"
        journal["actual_sha256"] = hashlib.sha256(final).hexdigest()
        journal["matched_blocks"] = 64 if plan.mode == "gen1a" else 63
        record()
        log(f"Selesai: {journal['matched_blocks']} blok cocok. UID hasil {current_uid}. Hasil: {session}")
        return InkReport(current_uid, str(session), True, tuple(written), plan.mode == "gen1a")
    except (Exception, KeyboardInterrupt) as exc:
        journal["status"] = "incomplete" if written or journal["pending_block"] is not None else "aborted_before_write"
        journal["error"] = str(exc)
        record()
        log(f"{journal['status']}: {exc}")
        raise InkError(f"{exc}\nBackup, key sebelum/sesudah, dan journal: {session}") from exc


def export_reference(source: InkReference, filename: str):
    _check_reference(source)
    path = Path(filename).expanduser().resolve()
    if path.suffix.lower() != ".bin":
        raise InkError("Pilih nama file dump dengan ekstensi .bin.")
    keypath = path.with_name(path.stem + "-key.bin")
    if path.exists() or keypath.exists():
        raise InkError("File sudah ada. Pilih nama baru agar acuan lama tetap tersedia.")
    path.write_bytes(source.data)
    keypath.write_bytes(keyfile(source.data))
    return str(path), str(keypath)
