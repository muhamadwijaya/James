"""Operasi tingkat tinggi: scan kartu, tampilkan data, pulihkan key.

Setiap fungsi hanya menyusun perintah PM3 standar dan mengembalikan
hasil yang sudah diparse. Tidak ada logika kriptografi di sini —
pencarian key memakai tool bawaan firmware Iceman (fchk/autopwn),
yang mengandalkan dictionary dan serangan yang sudah dipublikasikan.
"""

from __future__ import annotations

from .client import PM3Client, PM3Result
from . import parse


def check_device(client: PM3Client) -> PM3Result:
    """Cek koneksi & tuning antena (`hw version`, `hw tune`)."""
    return client.run("hw version", "hw tune")


def scan_auto(client: PM3Client) -> dict:
    """Deteksi otomatis kartu di LF maupun HF.

    Menjalankan `hf search` lalu `lf search` dan menggabungkan hasilnya.
    """
    hf = client.run("hf search")
    lf = client.run("lf search")

    result: dict = {"hf_raw": hf.stdout, "lf_raw": lf.stdout}
    result["hf"] = parse.parse_hf_identity(hf.stdout)
    result["lf_em410x"] = parse.parse_lf_em410x(lf.stdout)
    return result


def read_hf_14a(client: PM3Client) -> dict:
    """Baca identitas kartu ISO14443-A (MIFARE, NTAG, DESFire, dll.)."""
    res = client.run("hf 14a info")
    out = parse.parse_hf_identity(res.stdout)
    out["raw"] = res.stdout
    return out


def read_lf_em410x(client: PM3Client) -> dict:
    """Baca kartu EM4100/EM410x 125 kHz."""
    res = client.run("lf em 410x reader")
    return {"id": parse.parse_lf_em410x(res.stdout), "raw": res.stdout}


def recover_mifare_keys(client: PM3Client, dictionary: str | None = None,
                        timeout: float = 600.0) -> dict:
    """Pulihkan key MIFARE Classic untuk kartu MILIK SENDIRI.

    Memakai `hf mf autopwn` dari firmware Iceman, yang otomatis mencoba:
      * dictionary key umum (default keys pabrikan),
      * serangan darkside/nested/hardnested yang sudah dipublikasikan,
    lalu men-dump seluruh isi kartu memakai key yang ditemukan dan
    menyimpannya ke file (.bin/.json/.eml) di working dir client.

    Parameters
    ----------
    dictionary:
        Path file dictionary key opsional (`-f <file>`).
    timeout:
        hardnested bisa lama; default 10 menit.
    """
    cmd = "hf mf autopwn"
    if dictionary:
        cmd += f" -f {dictionary}"

    res = client.run(cmd, timeout=timeout)
    return {
        "keys": parse.parse_found_keys(res.stdout),
        "raw": res.stdout,
        "ok": res.ok,
    }


def dump_mifare(client: PM3Client, keyfile: str | None = None) -> PM3Result:
    """Dump isi MIFARE Classic memakai key yang sudah diketahui.

    Jika `keyfile` diberikan (file .bin hasil autopwn/fchk), dipakai
    lewat `-k <file>`; kalau tidak, PM3 memakai key default yang tersimpan.
    """
    cmd = "hf mf dump"
    if keyfile:
        cmd += f" -k {keyfile}"
    return client.run(cmd, timeout=120.0)
