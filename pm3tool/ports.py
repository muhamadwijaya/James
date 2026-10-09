"""Deteksi serial port yang tersedia (lintas platform, tanpa dependensi).

Windows: baca registry HKLM\\HARDWARE\\DEVICEMAP\\SERIALCOMM.
Linux/macOS: glob perangkat tty umum.
"""

from __future__ import annotations

import glob
import sys


def list_serial_ports() -> list[str]:
    if sys.platform.startswith("win"):
        return _windows_ports()
    return _posix_ports()


def _windows_ports() -> list[str]:
    try:
        import winreg
    except ImportError:
        return []
    ports: list[str] = []
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"HARDWARE\DEVICEMAP\SERIALCOMM")
    except OSError:
        return []
    try:
        i = 0
        while True:
            try:
                _name, value, _type = winreg.EnumValue(key, i)
            except OSError:
                break
            if value:
                ports.append(str(value))   # mis. "COM10"
            i += 1
    finally:
        winreg.CloseKey(key)
    # urutkan numerik: COM3 < COM10
    return sorted(set(ports), key=_com_sort_key)


def _com_sort_key(name: str):
    digits = "".join(c for c in name if c.isdigit())
    return (int(digits) if digits else 0, name)


def _posix_ports() -> list[str]:
    patterns = [
        "/dev/ttyACM*", "/dev/ttyUSB*",
        "/dev/tty.usb*", "/dev/tty.SLAB*", "/dev/tty.wchusb*",
        "/dev/cu.usb*",
    ]
    out: list[str] = []
    for pat in patterns:
        out += glob.glob(pat)
    return sorted(set(out))
