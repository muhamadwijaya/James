"""Pemulihan key MIFARE Classic lewat READER (bukan dari kartu).

Berguna saat Anda lupa key tapi masih punya reader yang tahu key-nya.
Semua lewat perintah resmi firmware Iceman — gunakan hanya pada
reader/kartu milik sendiri.

Dua metode:

1. recover_via_reader()  — "reader attack" (mfkey32).
   PM3 menyamar sebagai kartu (`hf mf sim ... -x`). Saat reader asli
   mencoba autentikasi, PM3 mengumpulkan nonce (nr/ar) dan menghitung
   key yang dipakai reader. Tempelkan PM3 ke reader Anda.

2. sniff_and_crack()     — sadap lalu pecahkan.
   `hf 14a sniff` menyadap transaksi reader<->kartu asli, lalu
   `trace list -t mf` mendekode dan memulihkan key dari auth yang
   tertangkap (mfkey64).
"""

from __future__ import annotations

from .client import PM3Client
from . import parse


def recover_via_reader(client: PM3Client, uid: str | None = None,
                       store_keys: bool = True, timeout: float = 180.0) -> dict:
    """Reader attack (mfkey32): PM3 jadi kartu, peras key dari reader.

    Parameters
    ----------
    uid:
        UID yang disimulasikan (hex, mis. '2CD72F90'). Sebaiknya sama
        dengan kartu asli agar reader mau berinteraksi. Kosong = UID
        default simulator.
    store_keys:
        Tambah ``-e`` agar key yang ditemukan disimpan ke memori emulator.
    """
    cmd = "hf mf sim --1k -x"
    if uid:
        import re
        cmd += f" -u {re.sub(r'[^0-9A-Fa-f]', '', uid)}"
    if store_keys:
        cmd += " -e"
    res = client.run(cmd, timeout=timeout)
    return {
        "keys": parse.parse_mfkey_keys(res.stdout),
        "raw": res.stdout,
        "ok": res.ok,
    }


def sniff_14a(client: PM3Client, timeout: float = 180.0):
    """Sadap trafik ISO14443-A antara reader asli dan kartu.

    `hf 14a sniff` berjalan sampai tombol PM3 ditekan (atau timeout).
    Tempelkan kartu ke reader selama proses agar transaksi terekam.
    """
    return client.run("hf 14a sniff", timeout=timeout)


def crack_from_trace(client: PM3Client, timeout: float = 120.0) -> dict:
    """Dekode trace hasil sniff & pulihkan key (`trace list -t mf`)."""
    res = client.run("trace list -t mf", timeout=timeout)
    return {
        "keys": parse.parse_mfkey_keys(res.stdout),
        "raw": res.stdout,
        "ok": res.ok,
    }


def sniff_and_crack(client: PM3Client, sniff_timeout: float = 180.0,
                    crack_timeout: float = 120.0) -> dict:
    """Jalankan sniff lalu langsung decode+crack trace-nya."""
    sniff = sniff_14a(client, timeout=sniff_timeout)
    cracked = crack_from_trace(client, timeout=crack_timeout)
    cracked["sniff_raw"] = sniff.stdout
    return cracked
