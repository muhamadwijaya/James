"""Penyalinan data MIFARE 1K dari acuan, dengan backup dan verifikasi.

Tanpa profil, semua blok data mengikuti acuan. Profil opsional memilih byte
tertentu. UID, key, dan access bits target dipertahankan. Penyalinan tidak
menetapkan arti bisnis data atau menghitung MAC.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import dumpview, parse
from .client import PM3Client, PM3Result

CARD_SIZE = 1024
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


class RecycleError(RuntimeError):
    """Operasi dihentikan karena input, autentikasi, atau verifikasi gagal."""


@dataclass(frozen=True)
class BlockChange:
    block: int
    before: bytes
    after: bytes

    @property
    def offsets(self) -> tuple[int, ...]:
        return tuple(i for i, (a, b) in enumerate(zip(self.before, self.after)) if a != b)


@dataclass(frozen=True)
class WritePlan:
    profile_name: str
    uid: str
    before: bytes = field(repr=False)
    after: bytes = field(repr=False)
    keyfile: bytes = field(repr=False)
    changes: tuple[BlockChange, ...]
    reference_hash: str
    key_type: str


@dataclass(frozen=True)
class WriteReport:
    uid: str
    verified_blocks: tuple[int, ...]
    session_dir: str
    verified: bool


def _data_block(block: int) -> bool:
    return 0 < block < 64 and block % 4 != 3


def _load_dump(path: str) -> bytes:
    if Path(path).suffix.lower() == ".json":
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            raise RecycleError("Dump JSON harus berupa objek blocks.")
        blocks = obj.get("blocks", {})
        if not isinstance(blocks, dict) or set(blocks) != {str(i) for i in range(64)}:
            raise RecycleError("Dump JSON harus memuat blok 0–63 secara lengkap.")
        if any(not isinstance(value, str) or len(bytes.fromhex(value)) != 16 for value in blocks.values()):
            raise RecycleError("Setiap blok pada dump JSON harus berukuran 16 byte.")
    data = dumpview.load_dump(path)
    if len(data) != CARD_SIZE:
        raise RecycleError("Write Data saat ini mendukung dump 1K lengkap (1024 byte).")
    # Dump dengan UID 7 byte tidak memakai layout block 0 ini.
    if data[4] != (data[0] ^ data[1] ^ data[2] ^ data[3]):
        raise RecycleError("Layout UID 4 byte/BCC pada dump tidak cocok. Periksa jenis kartu.")
    return data


def _normal_keys(raw: bytes) -> bytes:
    # Format PM3: seluruh key A, lalu seluruh key B. FM11RF08S dapat
    # menambahkan satu entri sektor backdoor (204 byte, 17 key per tipe).
    if len(raw) not in (192, 204):
        raise RecycleError("Key file 1K harus 192 atau 204 byte dari PM3.")
    half = len(raw) // 2
    return raw[:96] + raw[half:half + 96]


def _check_write_access(data: bytes, block: int, kind: str) -> None:
    """Decode access bits MIFARE Classic 1K (NXP, tabel akses blok data)."""
    start = ((block // 4) * 4 + 3) * 16
    b6, b7, b8 = data[start + 6:start + 9]
    c1, c2, c3 = b7 >> 4, b8 & 15, b8 >> 4
    if b6 & 15 != (c1 ^ 15) or b6 >> 4 != (c2 ^ 15) or b7 & 15 != (c3 ^ 15):
        raise RecycleError(f"Access bits sektor {block // 4} tidak valid.")
    index = block % 4
    rights = (((c1 >> index) & 1) << 2) | (((c2 >> index) & 1) << 1) | ((c3 >> index) & 1)
    allowed = {0: {"A", "B"}, 3: {"B"}, 4: {"B"}, 6: {"B"}}
    if kind not in allowed.get(rights, set()):
        raise RecycleError(f"Izin akses blok {block} tidak mengizinkan penulisan dengan key {kind}.")


def block_list(text: str) -> tuple[int, ...]:
    selected: set[int] = set()
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        if re.fullmatch(r"\d+-\d+", item):
            start, end = map(int, item.split("-"))
            if end < start or end > 63:
                raise RecycleError("Rentang blok tidak valid.")
            selected.update(range(start, end + 1))
        elif item.isdecimal():
            selected.add(int(item))
        else:
            raise RecycleError("Gunakan nomor blok dipisahkan koma atau rentang, misalnya 1-2.")
    if not selected or any(not _data_block(block) for block in selected):
        raise RecycleError("Pilih blok data 1–62. Blok 0 dan sector trailer dilindungi.")
    return tuple(sorted(selected))


def create_profile(reference: str, blocks: str, output: str,
                   name: str = "Profil penyalinan data") -> str:
    data = _load_dump(reference)
    selected = block_list(blocks)
    profile = {
        "schema_version": 1,
        "name": name,
        "reference_sha256": hashlib.sha256(data).hexdigest(),
        "block_masks": {str(block): "FF" * 16 for block in selected},
    }
    with Path(output).open("x", encoding="utf-8") as handle:
        json.dump(profile, handle, indent=2)
        handle.write("\n")
    return output


def build_plan(reference: str, target: str, keyfile: str, profile: str | None = None,
               key_type: str = "A") -> WritePlan:
    """Preview offline; profile=None menyalin semua blok data biasa.

    Hanya blok dengan byte berbeda masuk daftar tulis. Identitas dan seluruh
    sector trailer selalu diambil dari target, termasuk bila berbeda dari acuan.
    """
    if key_type not in ("A", "B"):
        raise RecycleError("Tipe key harus A atau B.")
    source, before = _load_dump(reference), _load_dump(target)
    keys = _normal_keys(Path(keyfile).read_bytes())
    for sector in range(16):
        trailer = before[(sector * 4 + 3) * 16:(sector * 4 + 4) * 16]
        if keys[sector * 6:sector * 6 + 6] != trailer[:6] or \
                keys[96 + sector * 6:102 + sector * 6] != trailer[10:16]:
            raise RecycleError(f"Key file tidak cocok dengan backup target pada sektor {sector}.")
    digest = hashlib.sha256(source).hexdigest()
    settings = json.loads(Path(profile).read_text(encoding="utf-8")) if profile is not None else {
        "schema_version": 1,
        "name": "Salin semua blok data dari acuan (tanpa profil)",
        "reference_sha256": digest,
        "block_masks": {str(block): "FF" * 16 for block in range(64) if _data_block(block)},
    }
    if not isinstance(settings, dict) or settings.get("schema_version") != 1:
        raise RecycleError("Profil harus menggunakan schema_version 1.")
    if settings.get("reference_sha256") != digest:
        raise RecycleError("Dump acuan tidak cocok dengan SHA-256 pada profil.")
    masks = settings.get("block_masks")
    if not isinstance(masks, dict) or not masks:
        raise RecycleError("Profil belum memiliki daftar blok/byte untuk reset.")
    after = bytearray(before)
    chosen: set[int] = set()
    for number, encoded in masks.items():
        if not isinstance(number, str) or not number.isdecimal() or str(int(number)) != number:
            raise RecycleError("Nomor blok pada profil harus berupa angka desimal tanpa nol awal.")
        block = int(number)
        if not _data_block(block):
            raise RecycleError(f"Blok {block} dilindungi atau berada di luar kartu 1K.")
        if not isinstance(encoded, str):
            raise RecycleError(f"Mask blok {block} harus berupa teks hex.")
        try:
            mask = bytes.fromhex(encoded)
        except ValueError as exc:
            raise RecycleError(f"Mask hex blok {block} tidak valid.") from exc
        if len(mask) != 16 or any(value not in (0, 255) for value in mask) or not any(mask):
            raise RecycleError(f"Mask blok {block} harus 16 byte 00/FF, minimal satu FF.")
        chosen.add(block)
        for offset, value in enumerate(mask):
            if value:
                position = block * 16 + offset
                after[position] = source[position]
    result = bytes(after)
    changes = tuple(BlockChange(block, before[block * 16:(block + 1) * 16],
                                result[block * 16:(block + 1) * 16])
                    for block in sorted(chosen)
                    if before[block * 16:(block + 1) * 16] != result[block * 16:(block + 1) * 16])
    for change in changes:
        _check_write_access(before, change.block, key_type)
    return WritePlan(str(settings.get("name", "Profil reset")), before[:4].hex().upper(),
                     before, result, keys, changes, digest, key_type)


def format_plan(plan: WritePlan) -> str:
    lines = [f"Profil: {plan.profile_name}", f"UID target: {plan.uid}",
             f"Blok data yang berubah: {len(plan.changes)}", "UID, key, dan access bits dipertahankan."]
    for change in plan.changes:
        lines.extend((f"\nBlok {change.block}, posisi byte: {', '.join(map(str, change.offsets))}",
                      f"  Sebelum: {change.before.hex(' ').upper()}",
                      f"  Sesudah: {change.after.hex(' ').upper()}"))
    return "\n".join(lines)


def _quoted_path(path: Path) -> str:
    value = str(path.resolve()).replace("\\", "/")
    if any(character in value for character in ('"', ';', '\r', '\n')):
        raise RecycleError("Path berkas mengandung karakter yang tidak didukung client PM3.")
    return '"' + value + '"'


def _text(result: PM3Result) -> str:
    return _ANSI.sub("", result.stdout + "\n" + result.stderr)


def _identity(client: PM3Client, uid: str) -> None:
    result = client.run("hf 14a info", timeout=30)
    actual = parse.parse_uid(_text(result))
    if not result.ok or actual != uid:
        raise RecycleError(f"UID kartu terpasang {actual or 'tidak terbaca'} tidak cocok dengan target {uid}.")


def _read_block(client: PM3Client, block: int, key: str, kind: str) -> bytes:
    result = client.run(f"hf mf rdbl --blk {block} -{kind.lower()} -k {key}", timeout=30)
    if result.ok:
        for line in _text(result).splitlines():
            parts = line.split("|")
            for index in range(1, len(parts)):
                number = re.sub(r"^\s*\[[^]]+\]\s*", "", parts[index - 1]).strip()
                if not number.isdecimal() or int(number) != block:
                    continue
                value = parts[index].strip()
                if re.fullmatch(r"(?:[0-9A-Fa-f]{2}\s+){15}[0-9A-Fa-f]{2}", value):
                    return bytes.fromhex(value)
    raise RecycleError(f"Pembacaan blok {block} gagal atau format output belum dikenali.")


def _dump(client: PM3Client, keys: Path, stem: Path) -> bytes:
    result = client.run(f"hf mf dump --1k -k {_quoted_path(keys)} -f {_quoted_path(stem)}", timeout=180)
    text = _text(result)
    path = stem.with_suffix(".bin")
    if not result.ok or "Succeeded in dumping all blocks" not in text or \
            re.search(r"\[(?:!|-)\][^\n]*\b(skip|failed|fail|timeout|time out|aborted)\b", text, re.IGNORECASE) or \
            not path.is_file():
        raise RecycleError("Backup/verifikasi penuh gagal. Periksa key dan izin baca seluruh blok.")
    return _load_dump(str(path))


def execute_plan(client: PM3Client, plan: WritePlan, backup_dir: str,
                 confirm_uid: str, emit=None) -> WriteReport:
    """Backup kartu live, cek baseline, tulis, lalu verifikasi seluruh dump.

    Gagal di tengah proses dicatat sebagai incomplete; tidak ada rollback
    otomatis. Backup asli dan journal tetap tersedia untuk pemulihan.
    """
    if confirm_uid.strip().upper() != plan.uid:
        raise RecycleError("Konfirmasi UID harus sama dengan UID pada preview.")
    if not plan.changes:
        raise RecycleError("Tidak ada perubahan untuk ditulis.")
    # Validasi ulang objek rencana sebelum mengakses kartu.
    if len(plan.before) != CARD_SIZE or len(plan.after) != CARD_SIZE or len(plan.keyfile) != 192:
        raise RecycleError("Ukuran rencana penulisan tidak valid.")
    changed = {i for i in range(64) if plan.before[i * 16:(i + 1) * 16] != plan.after[i * 16:(i + 1) * 16]}
    if changed != {change.block for change in plan.changes} or len(changed) != len(plan.changes) or \
            any(not _data_block(b) for b in changed):
        raise RecycleError("Rencana memuat perubahan di luar blok data yang diizinkan.")
    for change in plan.changes:
        _check_write_access(plan.before, change.block, plan.key_type)
        if change.before != plan.before[change.block * 16:(change.block + 1) * 16] or \
                change.after != plan.after[change.block * 16:(change.block + 1) * 16]:
            raise RecycleError("Isi perubahan tidak cocok dengan rencana.")
    session = Path(backup_dir).expanduser().resolve() / (
        plan.uid + "_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8])
    _quoted_path(session)
    session.mkdir(parents=True)
    keys = session / "target-key.bin"
    keys.write_bytes(plan.keyfile)
    (session / "expected.bin").write_bytes(plan.after)
    verified: list[int] = []
    journal = {
        "uid": plan.uid, "profile": plan.profile_name, "status": "preflight",
        "reference_sha256": plan.reference_hash,
        "blocks": [change.block for change in plan.changes], "verified_blocks": verified,
        "expected_sha256": hashlib.sha256(plan.after).hexdigest(), "pending_block": None,
    }

    def record() -> None:
        temporary = session / "journal.tmp"
        temporary.write_text(json.dumps(journal, indent=2), encoding="utf-8")
        temporary.replace(session / "journal.json")

    def notify(message: str) -> None:
        if emit:
            emit(message + "\n")

    record()
    try:
        _identity(client, plan.uid)
        notify("Membuat backup lengkap kartu terpasang sebelum penulisan…")
        backup = _dump(client, keys, session / "before")
        if backup != plan.before:
            raise RecycleError("Data kartu berubah sejak backup target dibuat. Buat dump target baru dan ulangi preview.")
        journal["backup_sha256"] = hashlib.sha256(backup).hexdigest()
        # Baca semua blok yang akan ditulis sebelum memulai penulisan.
        for change in plan.changes:
            offset = (0 if plan.key_type == "A" else 96) + (change.block // 4) * 6
            key = plan.keyfile[offset:offset + 6].hex().upper()
            if _read_block(client, change.block, key, plan.key_type) != change.before:
                raise RecycleError(f"Preflight blok {change.block} tidak cocok dengan backup.")
        journal["status"] = "writing"
        record()
        for change in plan.changes:
            _identity(client, plan.uid)
            offset = (0 if plan.key_type == "A" else 96) + (change.block // 4) * 6
            key = plan.keyfile[offset:offset + 6].hex().upper()
            if _read_block(client, change.block, key, plan.key_type) != change.before:
                raise RecycleError(f"Blok {change.block} berubah sebelum penulisan.")
            journal["pending_block"] = change.block
            record()
            result = client.run(f"hf mf wrbl --blk {change.block} -{plan.key_type.lower()} -k {key} "
                                f"-d {change.after.hex().upper()}", timeout=30)
            if not result.ok or not re.search(r"\bWrite\s*\(\s*ok\s*\)", _text(result), re.IGNORECASE):
                raise RecycleError(f"PM3 tidak mengonfirmasi keberhasilan tulis blok {change.block}.")
            _identity(client, plan.uid)
            if _read_block(client, change.block, key, plan.key_type) != change.after:
                raise RecycleError(f"Verifikasi hasil tulis blok {change.block} gagal.")
            verified.append(change.block)
            journal["pending_block"] = None
            record()
            notify(f"Blok {change.block}: ditulis dan dibaca ulang, cocok.")
        _identity(client, plan.uid)
        final = _dump(client, keys, session / "after")
        if final != plan.after:
            raise RecycleError("Verifikasi dump akhir tidak cocok dengan rencana.")
        journal["status"] = "verified"
        journal["actual_sha256"] = hashlib.sha256(final).hexdigest()
        record()
        notify(f"Penulisan data terverifikasi. Backup dan hasil: {session}")
        return WriteReport(plan.uid, tuple(verified), str(session), True)
    except (Exception, KeyboardInterrupt) as exc:
        journal["status"] = "incomplete" if journal["pending_block"] is not None or verified else "aborted_before_write"
        journal["error"] = str(exc)
        record()
        raise RecycleError(f"{exc}\nStatus: {journal['status']}. Backup/journal: {session}") from exc
