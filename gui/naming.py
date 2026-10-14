"""Rename rule, mirrored from backend/PhotoProcessor.cs (used only for the preview in the GUI).

    received : "3975 264 812_2026_10_10_00_08_46.jpg"                       -> code "3975264812"
               "https&&&aslibos.com&scan&BXXAXESPP2026_10_14_12_16_53.jpg"  -> code "BXXAXESPP"
    saved as : "LINE-ID_YYYYMMDD_HHMMSS_CODE.jpg", e.g. "00001_20261014_121653_BXXAXESPP.jpg"

The date/time YYYY_MM_DD_HH_MM_SS is found first; the code is the text right before it, after
the last separator (& / \\ = ? # _ : ;), so URL prefixes are ignored and the code may have any length.
"""
from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import unquote

EXAMPLE_INCOMING = "https&&&aslibos.com&scan&BXXAXESPP2026_10_14_12_16_53.jpg"

_INCOMING = re.compile(
    r"^(?P<prefix>.*?)(?P<y>[0-9]{4})[_-](?P<mo>[0-9]{2})[_-](?P<d>[0-9]{2})"
    r"[_-](?P<h>[0-9]{2})[_-](?P<mi>[0-9]{2})[_-](?P<s>[0-9]{2})(?P<rest>[^.]*)(?P<ext>\.[A-Za-z0-9]+)?\s*$"
)
_INVALID = set('\\/:*?"<>|')
_CODE_SEPARATORS = "&/\\=?#_:;"


def clean_code(raw: str) -> str:
    return "".join(c for c in raw if not (c.isspace() or c == "_" or c in _INVALID or ord(c) < 32))


def clean_line_id(raw: str) -> str:
    return "".join(c for c in raw if not (c.isspace() or c in _INVALID or ord(c) < 32))


def extract_code(prefix: str) -> str:
    text = unquote(prefix) if "%" in prefix else prefix
    text = text.rstrip("_- \t")
    cut = max(text.rfind(c) for c in _CODE_SEPARATORS)
    if cut >= 0:
        text = text[cut + 1:]
    return clean_code(text)


def build_name(incoming: str, line_id: str) -> str | None:
    """Return the new file name, or None when ``incoming`` does not match the format."""
    m = _INCOMING.match(incoming or "")
    if not m:
        return None
    code = extract_code(m.group("prefix"))
    if not code:
        return None
    try:
        ts = datetime(int(m.group("y")), int(m.group("mo")), int(m.group("d")),
                      int(m.group("h")), int(m.group("mi")), int(m.group("s")))
    except ValueError:
        return None
    ext = (m.group("ext") or ".jpg").lower()
    return f"{clean_line_id(line_id)}_{ts:%Y%m%d_%H%M%S}_{code}{ext}"
