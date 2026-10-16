"""Hardware ID: a stable fingerprint of this machine, so a license is locked to one PC.

Windows: registry MachineGuid + C: volume serial + primary MAC.
Other OS (used for development/tests): /etc/machine-id (or hostname) + primary MAC.
All hashed with SHA-256 so the raw identifiers never leave the machine.
"""
from __future__ import annotations

import hashlib
import os
import sys
import uuid


def _windows_parts() -> list[str]:
    parts: list[str] = []
    try:
        import winreg  # type: ignore
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
            parts.append("mg:" + str(winreg.QueryValueEx(key, "MachineGuid")[0]))
    except Exception:
        pass
    try:
        import ctypes
        serial = ctypes.c_uint()
        system = os.environ.get("SystemDrive", "C:") + "\\"
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            ctypes.c_wchar_p(system), None, 0, ctypes.byref(serial), None, None, None, 0)
        if ok:
            parts.append("vs:" + format(serial.value, "08X"))
    except Exception:
        pass
    return parts


def _unix_parts() -> list[str]:
    parts: list[str] = []
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            with open(path, "r", encoding="ascii") as f:
                value = f.read().strip()
            if value:
                parts.append("mid:" + value)
                break
        except OSError:
            continue
    if not parts:
        import socket
        parts.append("host:" + socket.gethostname())
    return parts


def _mac_part() -> str:
    node = uuid.getnode()
    # uuid.getnode() sets the multicast bit when it had to invent a random address: skip those.
    if (node >> 40) & 1:
        return ""
    return "mac:" + format(node, "012X")


def raw_fingerprint() -> str:
    parts = _windows_parts() if sys.platform.startswith("win") else _unix_parts()
    mac = _mac_part()
    if mac:
        parts.append(mac)
    return "|".join(parts) if parts else "unknown"


def hwid() -> str:
    """64-char lowercase hex SHA-256 of the machine fingerprint."""
    return hashlib.sha256(raw_fingerprint().encode("utf-8")).hexdigest()


def display_id(value: str | None = None) -> str:
    """Short, human-readable form of the HWID for showing/copying (first 20 hex, grouped)."""
    h = (value or hwid())[:20].upper()
    return "-".join(h[i:i + 5] for i in range(0, len(h), 5))
