"""Katalog metode resmi PM3, parameter, dukungan versi, dan laporan recovery.

Metode mengikuti bagian recovery RRG cmdhfmf serta tool nonce/reader resminya.
Wrapper tidak membuat algoritme baru atau menjamin key akan ditemukan.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import parse
from .client import PM3Client, PM3Result
from .process import run_process


class RecoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class Method:
    id: str
    label: str
    command: str
    description: str
    defaults: str = ""
    external: bool = False


METHODS = (
    Method("autopwn", "Autopwn — recovery otomatis", "hf mf autopwn", "Menggabungkan dictionary dan serangan yang cocok dengan kartu. Simpan log bila belum lengkap."),
    Method("fchk", "FCHK — dictionary cepat", "hf mf fchk", "Menguji key umum, key yang sudah diketahui, dan dictionary.", "--dump"),
    Method("chk", "CHK — dictionary biasa/legacy", "hf mf chk", "Pemeriksaan key alternatif untuk kartu yang tidak cocok dengan FCHK.", "--dump"),
    Method("darkside", "Darkside", "hf mf darkside", "Memerlukan kartu dengan kerentanan nonce/PRNG yang sesuai."),
    Method("nested", "Nested", "hf mf nested", "Memerlukan satu key valid dan PRNG yang rentan. Blok target opsional untuk recovery satu key.", "--dump"),
    Method("hardnested", "Hardnested — live / nonce offline", "hf mf hardnested", "Gunakan key valid, blok input dan target. Pilih file nonce dan mode offline untuk data yang sudah dikumpulkan."),
    Method("staticnested", "Staticnested", "hf mf staticnested", "Memerlukan satu key valid pada kartu dengan static nonce.", "--dumpkeys"),
    Method("sen", "SEN — FM11RF08S static encrypted nonce", "hf mf sen", "Recovery khusus static encrypted nonce FM11RF08S; tersedia pada client RRG yang mendukungnya."),
    Method("brute", "Smart brute force", "hf mf brute", "Menguji pola pembangkitan key yang lemah, bukan pencarian universal seluruh key 48-bit.", "--dump"),
    Method("nack", "NACK — pemeriksaan kerentanan", "hf mf nack", "Diagnostik NACK bug; pemeriksaan ini sendiri tidak menjamin recovery key."),
    Method("decrypt", "Decrypt Crypto1 dari trace", "hf mf decrypt", "Masukkan --nt, --ar, --at, dan -d sesuai trace. Ini analisis data, bukan recovery universal."),
    Method("supercard", "Supercard — ekstraksi key", "hf mf supercard", "Memerlukan super card yang sesuai. Tanpa opsi reset atau perubahan UID."),
    Method("keygen", "Keygen — KDF yang dikenal", "hf mf keygen", "Menghasilkan kandidat dari KDF yang dikenal. Kandidat perlu diuji dengan FCHK/CHK; hasil keygen tidak dianggap key terverifikasi."),
    Method("info", "Diagnostik kartu / PRNG", "hf mf info", "Periksa jenis kartu dan karakteristik nonce sebelum memilih metode."),
    Method("isen", "ISEN — diagnostik static encrypted nonce", "hf mf isen", "Analisis sifat nonce; parameter lanjutan mengikuti Help client."),
    Method("collect", "Kumpulkan nonce FM11RF08S", "hf mf isen", "Kumpulkan data nonce FM11RF08S untuk analisis berikutnya. Gunakan key backdoor yang sesuai.", "--collect_fm11rf08s"),
    Method("reader", "Reader attack — mfkey32", "hf mf sim", "PM3 menjadi kartu. Tempelkan PM3 ke reader yang menyimpan key; UID dapat diisi.", "-x -e"),
    Method("reader_nested", "Nested reader attack", "hf mf sim", "Memerlukan nt dan nt_enc yang sudah dimuat di emulator; lihat Help -y.", "-y -e"),
    Method("sniff", "Sniff lalu analisis trace", "hf 14a sniff", "Rekam transaksi kartu-reader. Tekan tombol PM3 untuk selesai; kemudian trace dianalisis."),
    Method("trace", "Analisis trace — mfkey64", "trace list", "Analisis trace yang tersimpan pada PM3, atau tambahkan parameter file trace dari Help.", "-t mf"),
    Method("fm11script", "Script FM11RF08S recovery", "script run fm11rf08s_recovery.py", "Alternatif script resmi; memerlukan Python PM3 dan tool staticnested pendukung.", "-x -y"),
    Method("script", "Script recovery lain pada instalasi PM3", "script run", "Isi nama script dan argumennya. Daftar script dapat dilihat melalui tombol Daftar script."),
    Method("eload", "Muat data emulator untuk reader attack", "hf mf eload", "Muat dump/nonce emulator sebelum nested reader attack. Pilih file dan lihat Help."),
    Method("ekeyprn", "Tampilkan key memori emulator", "hf mf ekeyprn", "Tampilkan key hasil reader attack di memori emulator; key emulator bukan bukti autentikasi kartu."),
    *(Method(tool, "Tool offline — " + tool, tool,
             "Pilih executable resmi yang terpasang; masukkan nonce/transkrip sesuai Help tool. Tidak memerlukan COM.", external=True)
      for tool in ("mfkey32", "mfkey32v2", "mfkey64", "nonce2key", "staticnested_1nt",
                   "staticnested_2x1nt_rf08s", "staticnested_2x1nt_rf08s_1key")),
)
BY_ID = {method.id: method for method in METHODS}
SIZES = {"mini": 5, "1k": 16, "2k": 32, "4k": 40}
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_UNSUPPORTED = re.compile(r"unknown command|invalid command|not available|not supported|cannot find|can't find|command not found|unrecognized command", re.I)
_SECTOR_KEY = re.compile(r"(?:key\s+sec(?:tor)?|sector)\s*(\d+)\s+key\s*([AB])\s*=\s*([0-9a-f]{12})\b", re.I)
_FOUND = re.compile(r"\bfound\s+(?:valid\s+)?key\s*:?\s*(?:[AB]\s+)?\[?([0-9a-f]{12})\b", re.I)
_KEY_FOUND = re.compile(r"\bkey\s+found\s*[:=]?\s*\[?([0-9a-f]{12})\b", re.I)


def clean_hex(value: str, lengths: tuple[int, ...], name: str) -> str:
    compact = re.sub(r"[\s:]", "", value).upper()
    if compact and (len(compact) not in lengths or not re.fullmatch(r"[0-9A-F]+", compact)):
        raise RecoveryError(f"{name} harus hex dengan panjang {', '.join(map(str, lengths))} digit.")
    return compact


def single_command(command: str) -> str:
    if not command.strip() or any(char in command for char in (";", "\r", "\n", "\x00")):
        raise RecoveryError("Masukkan satu perintah recovery tanpa pemisah perintah atau baris baru.")
    return command.strip()


def quoted_path(value: str) -> str:
    if any(c in value for c in ('"', ';', '\r', '\n', '\x00')):
        raise RecoveryError("Nama file mengandung karakter yang tidak didukung.")
    return '"' + str(Path(value).expanduser().resolve()).replace('\\', '/') + '"'


def build_command(method: Method, *, size="1k", key="", key_type="A", block=0,
                  target=4, target_type="A", single_target=False, uid="", dictionary="",
                  datafile="", offline=False, extra="") -> str:
    if size not in SIZES or key_type not in ("A", "B") or target_type not in ("A", "B"):
        raise RecoveryError("Ukuran kartu atau tipe key tidak valid.")
    key_methods = {"autopwn", "fchk", "chk", "nested", "hardnested", "staticnested", "isen", "collect"}
    key = clean_hex(key, (12,), "Key") if method.id in key_methods else ""
    uid = clean_hex(uid, (8, 14, 20), "UID") if method.id in {"reader", "reader_nested", "keygen"} else ""
    if block < 0 or target < 0 or block > 255 or target > 255:
        raise RecoveryError("Nomor blok harus 0–255.")
    parts = [method.command]
    if method.id in {"autopwn", "fchk", "chk", "nested", "staticnested", "brute", "reader", "reader_nested"}:
        parts.append("--" + size)
    if method.id in {"nested", "staticnested"} and not key:
        raise RecoveryError("Metode ini memerlukan satu key valid beserta blok dan tipe key asal.")
    if method.id in {"nested", "hardnested", "staticnested"} and not offline:
        if key:
            parts.extend(["--blk", str(block), "-" + key_type.lower(), "-k", key])
        if method.id == "hardnested" or (method.id == "nested" and single_target):
            parts.extend(["--tblk", str(target), "--t" + target_type.lower()])
    elif method.id == "autopwn" and key:
        sector = block // 4 if block < 128 else 32 + (block - 128) // 16
        parts.extend(["-s", str(sector), "-" + key_type.lower(), "-k", key])
    elif method.id in {"fchk", "chk"} and key:
        parts.extend(["-k", key])
    elif method.id == "darkside":
        parts.extend(["--blk", str(target)])
        if target_type == "B":
            parts.append("-b")
    elif method.id in {"isen", "collect"} and key:
        parts.extend(["-k", key])
    if dictionary and method.id in {"autopwn", "fchk", "chk"}:
        parts.extend(["-f", quoted_path(dictionary)])
    if uid and method.id in {"reader", "reader_nested", "keygen"}:
        parts.extend(["-u", uid])
    if method.id == "hardnested" and datafile:
        parts.extend(["-f", quoted_path(datafile), "-r" if offline else "-w"])
    elif method.id == "hardnested" and offline:
        raise RecoveryError("Pilih file nonce untuk hardnested offline.")
    elif method.id in {"collect", "eload"} and datafile:
        parts.extend(["-f", quoted_path(datafile)])
    if method.defaults:
        parts.append(method.defaults)
    if extra.strip():
        parts.append(extra.strip())
    return single_command(" ".join(parts))


def parse_results(text: str) -> tuple[list[dict], list[str]]:
    text = _ANSI.sub("", text)
    found = {(int(row["sector"]), row["type"]): row["key"] for row in parse.parse_found_keys(text)}
    for sector, kind, key in _SECTOR_KEY.findall(text):
        found[(int(sector), kind.upper())] = key.upper()
    rows = [{"sector": sector, "type": kind, "key": key} for (sector, kind), key in sorted(found.items())]
    unique = list(dict.fromkeys([row["key"] for row in rows] +
                              [key.upper() for key in _FOUND.findall(text) + _KEY_FOUND.findall(text)]))
    return rows, unique


def discover(client: PM3Client, emit=None, cancel=None) -> list[Method]:
    result = client.run_live("hf mf help", timeout=45, emit=emit, cancel=cancel)
    if not result.ok:
        raise RecoveryError(result.stderr or "Daftar metode tidak dapat dibaca dari client.")
    methods = []
    section = False
    for line in _ANSI.sub("", result.stdout).splitlines():
        if "---" in line and "recovery" in line.lower():
            section = True
            continue
        if section and "---" in line:
            break
        match = re.match(r"\s*(?:\[[+=]\]\s*)?([a-z][a-z0-9_]*)\s+(?:[YN]\s+)?(.+)", line)
        if section and match:
            name, description = match.groups()
            if name not in BY_ID:
                methods.append(Method(name, name + " — dari client PM3", "hf mf " + name, description))
    return methods


def find_tool(name: str, client: PM3Client) -> str:
    found = shutil.which(name) or shutil.which(name + ".exe")
    if found:
        return found
    if client.available():
        parents = list(Path(client.binary).resolve().parents)[:6]
        for root in parents:
            for directory in (Path("."), Path("tools/mfc/card_reader"), Path("tools/mfc/card_only"),
                              Path("client/build"), Path("client"), Path("tools")):
                for suffix in (".exe", ""):
                    candidate = root / directory / (name + suffix)
                    if candidate.is_file():
                        return str(candidate)
    raise RecoveryError(f"Tool {name} belum ditemukan. Pilih executable dari instalasi Proxmark3 Anda.")


def method_help(client: PM3Client, method: Method, *, executable="", offline=False, emit=None, cancel=None) -> PM3Result:
    if method.external:
        binary = executable or find_tool(method.command, client)
        return run_process([binary, "--help"], method.command + " --help", timeout=30,
                           env=client._augmented_env(), emit=emit, cancel=cancel)
    return client.run_live(method.command + " -h", timeout=45, emit=emit, cancel=cancel, offline=offline)


def run_recovery(client: PM3Client, method: Method, command: str, *, timeout=7200,
                 output_dir="recovery_sessions", executable="", offline=False,
                 size="1k", emit=None, cancel: threading.Event | None = None) -> dict:
    command = single_command(command)
    if not (command == method.command or command.startswith(method.command + " ")):
        raise RecoveryError("Perintah harus diawali metode recovery yang dipilih.")
    if size not in SIZES:
        raise RecoveryError("Ukuran kartu tidak valid.")
    if timeout <= 0:
        raise RecoveryError("Batas waktu harus lebih besar dari nol.")
    session = Path(output_dir).expanduser().resolve() / (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex[:8])
    session.mkdir(parents=True)
    chunks: list[str] = []

    def log(text):
        chunks.append(text)
        with (session / "session.log").open("a", encoding="utf-8") as handle:
            handle.write(text)
        if emit:
            emit(text)

    log("Metode: " + method.label + "\nPerintah: " + command + "\n")
    result = None
    error = None
    status = "failed"
    try:
        if method.external:
            binary = executable or find_tool(method.command, client)
            args = shlex.split(command[len(method.command):].strip())
            result = run_process([binary, *args], command, timeout=timeout, cwd=str(session),
                                 env=client._augmented_env(), emit=log, cancel=cancel)
        else:
            # Help bukan prasyarat eksekusi: beberapa client mengembalikan
            # kode nonzero saat menampilkan bantuan. Jalankan operasi langsung.
            if cancel and cancel.is_set():
                raise RecoveryError("Dibatalkan sebelum recovery dimulai.")
            log("\n=== Recovery dimulai ===\n")
            # Pertahankan direktori aplikasi seperti alur autopwn semula.
            # Log sesi memakai path absolut; resource PM3 tetap dapat ditemukan.
            result = client.run_live(command, timeout=timeout, emit=log,
                                     cancel=cancel, offline=offline)
            if method.id == "sniff" and result.ok and not (cancel and cancel.is_set()):
                log("\n=== Analisis trace ===\n")
                traced = client.run_live("trace list -t mf", timeout=timeout,
                                         emit=log, cancel=cancel)
                result = PM3Result(command, result.stdout + traced.stdout, traced.stderr, traced.returncode)
        status = "completed" if result.ok and not _UNSUPPORTED.search(result.stdout) else "failed"
        if result.returncode in (124, 130):
            status = "timeout" if result.returncode == 124 else "cancelled"
    except (Exception, KeyboardInterrupt) as exc:
        error = "Dibatalkan oleh pengguna." if isinstance(exc, KeyboardInterrupt) else str(exc)
        log("ERROR: " + error + "\n")
        if isinstance(exc, KeyboardInterrupt) or (cancel and cancel.is_set()):
            status = "cancelled"
    # Gunakan hanya output operasi; help/parameter tidak boleh dianggap key hasil recovery.
    raw = result.stdout if result else ""
    rows, keys = parse_results(raw) if method.id not in {"keygen", "ekeyprn"} else ([], [])
    if not rows and len(keys) == 1 and method.id in {"hardnested", "darkside", "nested"}:
        target = re.search(r"--tblk\s+(\d+)\b", command) if method.id != "darkside" else re.search(r"--blk\s+(\d+)\b", command)
        if target:
            number = int(target[1])
            sector = number // 4 if number < 128 else 32 + (number - 128) // 16
            kind = "B" if re.search(r"(?:--tb\b|-b\b)", command if method.id == "darkside" else command[command.find("--tblk"):]) else "A"
            rows = [{"sector": sector, "type": kind, "key": keys[0]}]
    uid = parse.parse_uid(raw)
    if method.id in {"reader", "reader_nested"}:
        match = re.search(r"(?:-u|--uid)\s+([0-9a-f]{8,20})\b", command, re.I)
        uid = match[1].upper() if match else uid
    required = {(sector, kind) for sector in range(SIZES[size]) for kind in ("A", "B")}
    recovered = {(row["sector"], row["type"]) for row in rows}
    missing = [{"sector": sector, "type": kind} for sector, kind in sorted(required - recovered)]
    has_sen = method.id in {"sen", "fm11script"} or (method.id == "autopwn" and (
        "FM11RF08S" in raw.upper() or any(row["sector"] == 32 for row in rows)))
    extra_required = {(32, kind) for kind in ("A", "B")} if size == "1k" and has_sen else set()
    if method.id == "fm11script" and re.search(r"(?:^|\s)(?:-n|--no-oob)(?:\s|$)", command):
        extra_required = set()
    missing_extra = [{"sector": sector, "type": kind} for sector, kind in sorted(extra_required - recovered)]
    # Autopwn dapat melewati serangan yang tidak cocok, lalu berhasil lewat
    # serangan lain. Pesan "not supported" dari langkah itu bukan kegagalan sesi.
    if status == "failed" and result and result.ok and keys and not error:
        status = "completed"
    if status == "completed" and method.id not in {"info", "isen", "collect", "nack", "keygen", "eload", "ekeyprn"}:
        status = "keys_found" if keys else "no_keys"
    if status == "failed" and not error:
        problem = [line.strip() for line in _ANSI.sub("", raw).splitlines()
                   if _UNSUPPORTED.search(line) or re.search(r"\b(error|failed|cannot|can't)\b", line, re.I)]
        error = result.stderr or (problem[-1] if problem else f"Client PM3 berhenti dengan kode {result.returncode}.")
    report = {"method": method.id, "command": command, "status": status, "uid": uid,
              "size": size, "keys": rows, "unique_keys": keys, "missing": missing,
              "expected_extra_sectors": sorted({sector for sector, _ in extra_required}), "missing_extra": missing_extra,
              "complete_normal_sectors": not missing, "session_dir": str(session),
              "returncode": result.returncode if result else None, "error": error or (result.stderr if result else None) or None,
              "note": "Hasil milik sesi ini; reader/nonce offline belum membuktikan autentikasi kartu target."}
    (session / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (session / "recovered.dic").write_text("".join(key + "\n" for key in keys), encoding="utf-8")
    log(f"\nStatus: {status}. Key unik: {len(keys)}. Key sektor: {len(required & recovered)}/{len(required)}.\n"
        + (f"Key sektor ekstra: {len(extra_required & recovered)}/{len(extra_required)}.\n" if extra_required else "") +
        f"Log, hasil, dan dictionary: {session}\n")
    return report


def run_auto(client: PM3Client, *, timeout=7200, output_dir="recovery_sessions",
             emit=None, cancel: threading.Event | None = None) -> dict:
    """Satu klik, tanpa bergantung pada kolom metode lanjutan atau Help.

    Gunakan perintah persis yang telah bekerja pada kartu 1K pengguna.
    Autopwn PM3 memilih dictionary dan serangan yang sesuai secara internal.
    """
    return run_recovery(client, BY_ID["autopwn"], "hf mf autopwn", timeout=timeout,
                        output_dir=output_dir, offline=False, size="1k", emit=emit, cancel=cancel)
