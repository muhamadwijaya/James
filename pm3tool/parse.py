"""Parsing output teks client Proxmark3 menjadi struktur Python.

Output PM3 hanya teks, jadi kita pakai regex yang toleran terhadap
perbedaan versi firmware. Kalau pola tidak cocok, field dikembalikan
``None`` daripada melempar error.
"""

from __future__ import annotations

import re

_UID_RE = re.compile(r"UID:?\s*([0-9A-Fa-f][0-9A-Fa-f ]+)")
_ATQA_RE = re.compile(r"ATQA:?\s*([0-9A-Fa-f ]+)")
_SAK_RE = re.compile(r"SAK:?\s*([0-9A-Fa-f]+)")
_EM410X_RE = re.compile(r"EM 410x ID\s*([0-9A-Fa-f]+)", re.IGNORECASE)
# baris key hasil recovery: "[+]  0 | A | FFFFFFFFFFFF | 1"
_KEY_RE = re.compile(
    r"^\s*\[\+\]\s*(\d+)\s*\|\s*([AB])\s*\|\s*([0-9A-Fa-f]{12})\s*\|",
    re.MULTILINE,
)
# key hasil mfkey32/mfkey64/sim, mis:
#   "[+]  Found valid key: ffffffffffff"
#   "[+] Found Key: A [ffffffffffff]"
#   "key: a0a1a2a3a4a5"
_MFKEY_RE = re.compile(
    r"(?:found\s+(?:valid\s+)?key|key)\s*:?\s*(?:[AB]\s*)?\[?([0-9A-Fa-f]{12})\]?",
    re.IGNORECASE,
)


def _clean_hex(s: str) -> str:
    return re.sub(r"[^0-9A-Fa-f]", "", s).upper()


def parse_uid(text: str) -> str | None:
    m = _UID_RE.search(text)
    return _clean_hex(m.group(1)) if m else None


def parse_hf_identity(text: str) -> dict[str, str | None]:
    """Ambil UID/ATQA/SAK dari output ``hf 14a reader``/``hf search``."""
    atqa = _ATQA_RE.search(text)
    sak = _SAK_RE.search(text)
    return {
        "uid": parse_uid(text),
        "atqa": _clean_hex(atqa.group(1)) if atqa else None,
        "sak": _clean_hex(sak.group(1)) if sak else None,
    }


def parse_lf_em410x(text: str) -> str | None:
    m = _EM410X_RE.search(text)
    return _clean_hex(m.group(1)) if m else None


def parse_found_keys(text: str) -> list[dict[str, str]]:
    """Ambil daftar key hasil ``hf mf autopwn``/``fchk``.

    Mengembalikan list of {sector, type (A/B), key}.
    """
    keys: list[dict[str, str]] = []
    for sector, ktype, key in _KEY_RE.findall(text):
        keys.append({"sector": sector, "type": ktype, "key": key.upper()})
    return keys


def parse_mfkey_keys(text: str) -> list[str]:
    """Ambil key hex (12 digit) dari output mfkey32/mfkey64/sim.

    Mengembalikan daftar key unik (urutan kemunculan dipertahankan).
    """
    seen: list[str] = []
    for key in _MFKEY_RE.findall(text):
        k = key.upper()
        if k not in seen:
            seen.append(k)
    return seen
