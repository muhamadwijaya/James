"""Temukan client dan port Proxmark3 tanpa membuka koneksi serial."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


# USB IDs yang juga digunakan launcher resmi RRG/Iceman (script `pm3`).
PM3_USB_IDS = {(0x9AC4, 0x4B8F), (0x2D2D, 0x504D)}
DEFAULT_PM3_ROOT = r"C:\ProxSpace\pm3\proxmark3"
IS_WINDOWS = os.name == "nt"


class PM3PortError(RuntimeError):
    """Port PM3 tidak ditemukan atau ada lebih dari satu perangkat."""


@dataclass(frozen=True)
class SerialPort:
    device: str
    description: str = ""
    hwid: str = ""

    @property
    def is_pm3(self) -> bool:
        text = f"{self.description} {self.hwid}"
        if re.search(r"prox[\s_-]*mark", text, re.IGNORECASE):
            return True
        return any(
            re.search(rf"VID_{vid:04X}&PID_{pid:04X}", text, re.IGNORECASE)
            or re.search(rf"VID:PID={vid:04X}:{pid:04X}", text, re.IGNORECASE)
            for vid, pid in PM3_USB_IDS
        )


@dataclass(frozen=True)
class Connection:
    binary: str | None
    port: str | None
    ports: tuple[SerialPort, ...]
    messages: tuple[str, ...]


def _binary_in(root: Path) -> str | None:
    names = ("proxmark3.exe", "pm3.exe", "pm3.bat", "pm3.cmd") if IS_WINDOWS else (
        "pm3", "proxmark3", "proxmark3.exe", "pm3.bat")
    # Layout make lama maupun layout client/build yang lebih baru.
    for directory in (root / "client", root / "client" / "build", root):
        for name in names:
            path = directory / name
            if path.is_file() and (IS_WINDOWS or name.endswith((".exe", ".bat"))
                                   or os.access(path, os.X_OK)):
                return str(path.resolve())
    return None


def _search_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("PM3_ROOT", "PROXSPACE"):
        if os.environ.get(key):
            root = Path(os.path.expandvars(os.environ[key])).expanduser()
            roots.extend((root, root / "pm3" / "proxmark3", root / "proxmark3"))
    if IS_WINDOWS:
        roots.extend((Path(DEFAULT_PM3_ROOT), Path(r"C:\ProxSpace\proxmark3")))
    for base in (Path.cwd(), Path(__file__).resolve().parent.parent,
                 Path.home(), Path.home() / "Desktop"):
        roots.extend((base, base / "proxmark3", base / "ProxSpace" / "pm3" / "proxmark3"))
    return list(dict.fromkeys(roots))


def find_pm3(binary: str | None = None) -> str | None:
    """Terima nama, file, atau folder; nilai auto/pm3 mencari instalasi umum.

    Path manual yang tidak valid dilaporkan sebagai gagal, bukan diganti
    diam-diam dengan instalasi lain. `auto` mengabaikan PM3_BINARY.
    """
    requested = binary if binary is not None else os.environ.get("PM3_BINARY", "pm3")
    requested = os.path.expandvars(requested.strip().strip('"')) or "pm3"
    if requested.lower() not in ("auto", "pm3"):
        path = Path(requested).expanduser()
        if path.is_dir():
            return _binary_in(path)
        if path.is_file():
            return str(path.resolve())
        return shutil.which(requested)
    for root in _search_roots():
        found = _binary_in(root)
        if found:
            return found
    names = ("proxmark3.exe", "pm3.exe", "pm3.bat", "pm3.cmd") if IS_WINDOWS else (
        "pm3", "proxmark3")
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def _serial_ports() -> list[SerialPort]:
    """pyserial opsional: enumerasi saja, tidak membuka perangkat."""
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    try:
        ports = []
        for item in list_ports.comports():
            metadata = " ".join(str(getattr(item, name, "") or "") for name in (
                "description", "manufacturer", "product"))
            hwid = item.hwid or ""
            if (item.vid, item.pid) in PM3_USB_IDS:
                hwid += f" VID:PID={item.vid:04X}:{item.pid:04X}"
            ports.append(SerialPort(item.device, metadata, hwid))
        return ports
    except (OSError, ValueError):
        return []


def _windows_ports() -> list[SerialPort]:
    """Windows bawaan, tanpa paket tambahan atau hak administrator."""
    powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
    if not powershell:
        return []
    script = r"""
 $ErrorActionPreference = 'Stop'
 [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
 $ports = @(Get-CimInstance -ClassName Win32_PnPEntity |
   Where-Object { $_.ConfigManagerErrorCode -eq 0 -and $_.Name -match '\(COM\d+\)' } |
   Select-Object Name, PNPDeviceID)
 ConvertTo-Json -InputObject $ports -Compress
 """
    try:
        result = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            return []
        records = json.loads(result.stdout.lstrip("\ufeff").strip() or "[]")
        if isinstance(records, dict):
            records = [records]
        ports = []
        for item in records or []:
            name = str(item.get("Name") or "")
            match = re.search(r"\((COM\d+)\)", name, re.IGNORECASE)
            if match:
                ports.append(SerialPort(match[1].upper(), name,
                                        str(item.get("PNPDeviceID") or "")))
        return ports
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, AttributeError):
        return []


def list_serial_ports() -> tuple[SerialPort, ...]:
    ports = _serial_ports()
    if IS_WINDOWS:
        # Lengkapi USB Serial Device yang namanya generik dengan ID Windows.
        ports.extend(_windows_ports())
    else:
        by_id = Path("/dev/serial/by-id")
        if by_id.is_dir():
            for item in by_id.iterdir():
                if item.exists():
                    ports.append(SerialPort(str(item.resolve()), item.name))
    merged: dict[str, SerialPort] = {}
    for port in ports:
        key = port.device.casefold() if IS_WINDOWS else port.device
        previous = merged.get(key)
        if previous:
            port = SerialPort(previous.device, f"{previous.description} {port.description}",
                              f"{previous.hwid} {port.hwid}")
        merged[key] = port
    return tuple(sorted(merged.values(), key=lambda p: re.sub(
        r"\d+", lambda m: m[0].zfill(8), p.device.casefold())))


def choose_pm3_port(ports: tuple[SerialPort, ...], *, required: bool = True) -> str | None:
    matches = [p.device for p in ports if p.is_pm3]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise PM3PortError("Beberapa Proxmark3 terdeteksi: " + ", ".join(matches)
                           + ". Pilih satu port secara manual.")
    if required:
        seen = ", ".join(p.device for p in ports) or "tidak ada"
        raise PM3PortError(
            "Port Proxmark3 belum terdeteksi. Sambungkan PM3, lalu klik Auto Detect. "
            f"Port serial yang terlihat: {seen}. Jika perlu, isi port secara manual.")
    return None


def detect_connection(binary: str | None = None, port: str | None = None) -> Connection:
    found = find_pm3(binary)
    ports = list_serial_ports()
    requested = binary or os.environ.get("PM3_BINARY", "pm3")
    location = DEFAULT_PM3_ROOT if requested.lower() in ("pm3", "auto") else requested
    messages = [f"PM3: {found}" if found else
                f"Client PM3 belum ditemukan. Periksa {location} atau pilih Browse."]
    selected = (port or "").strip() or None
    if selected:
        messages.append(f"Port manual: {selected}")
    else:
        try:
            selected = choose_pm3_port(ports)
            messages.append(f"Port PM3: {selected}")
        except PM3PortError as exc:
            messages.append(str(exc))
    return Connection(found, selected, ports, tuple(messages))
