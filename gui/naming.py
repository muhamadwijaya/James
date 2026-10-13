"""Rename rule, mirrored from backend/PhotoProcessor.cs (used only for the preview in the GUI).

    received : "3975 264 812_2026_10_10_00_08_46.jpg"   (CODE_YYYY_MM_DD_HH_MM_SS)
    saved as : "00001_20261010_000846_3975264812.jpg"  (LINE-ID_YYYYMMDD_HHMMSS_CODE)
"""
from __future__ import annotations

import re
from datetime import datetime

EXAMPLE_INCOMING = "3975 264 812_2026_10_10_00_08_46.jpg"

_INCOMING = re.compile(
    r"^\s*(?P<code>[^_]+?)\s*[_-]\s*(?P<y>[0-9]{4})[_-](?P<mo>[0-9]{2})[_-](?P<d>[0-9]{2})"
    r"[_-](?P<h>[0-9]{2})[_-](?P<mi>[0-9]{2})[_-](?P<s>[0-9]{2})(?P<rest>[^.]*)(?P<ext>\.[A-Za-z0-9]+)?\s*$"
)
_INVALID = set('\\/:*?"<>|')


def clean_code(raw: str) -> str:
    return "".join(c for c in raw if not (c.isspace() or c == "_" or c in _INVALID or ord(c) < 32))


def clean_line_id(raw: str) -> str:
    return "".join(c for c in raw if not (c.isspace() or c in _INVALID or ord(c) < 32))


def build_name(incoming: str, line_id: str) -> str | None:
    """Return the new file name, or None when ``incoming`` does not match the format."""
    m = _INCOMING.match(incoming or "")
    if not m:
        return None
    code = clean_code(m.group("code"))
    if not code:
        return None
    try:
        ts = datetime(int(m.group("y")), int(m.group("mo")), int(m.group("d")),
                      int(m.group("h")), int(m.group("mi")), int(m.group("s")))
    except ValueError:
        return None
    ext = (m.group("ext") or ".jpg").lower()
    return f"{clean_line_id(line_id)}_{ts:%Y%m%d_%H%M%S}_{code}{ext}"
