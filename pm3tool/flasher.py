"""Flashing firmware Proxmark3 lewat tool resmi.

Tool ini TIDAK berisi firmware sendiri. Flashing dilakukan memakai
script/binary resmi dari client Iceman/RRG:

  * ``pm3-flash-all``        -> bootrom + fullimage (disarankan)
  * ``pm3-flash-fullimage``  -> hanya OS + FPGA image
  * ``pm3-flash-bootrom``    -> hanya bootrom
  * ``flasher``              -> flasher mentah dengan file .elf eksplisit

File firmware (``bootrom.elf`` & ``fullimage.elf``) berasal dari hasil
build repo resmi atau dari paket instalasi Iceman. Lihat ``firmware.py``
untuk membangun/menemukannya.

PERINGATAN: flash hanya perangkat Proxmark3 milik Anda sendiri. Firmware
yang salah/putus di tengah bisa membuat perangkat perlu recovery lewat
bootrom (tahan tombol saat colok).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class FlashResult:
    command: str
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _tool(name: str) -> str | None:
    """Cari script/binary flashing di PATH (termasuk .bat di Windows)."""
    for candidate in (name, name + ".bat", name + ".sh"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def _run(argv: list[str], timeout: float) -> FlashResult:
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    return FlashResult(
        command=" ".join(argv),
        stdout=proc.stdout,
        stderr=proc.stderr,
        returncode=proc.returncode,
    )


def flash_all(port: str | None = None, timeout: float = 300.0) -> FlashResult:
    """Flash bootrom + fullimage memakai ``pm3-flash-all`` (disarankan)."""
    tool = _tool("pm3-flash-all")
    if not tool:
        return _missing("pm3-flash-all")
    argv = [tool] + ([port] if port else [])
    return _run(argv, timeout)


def flash_fullimage(port: str | None = None, timeout: float = 300.0) -> FlashResult:
    """Flash hanya OS + FPGA image memakai ``pm3-flash-fullimage``."""
    tool = _tool("pm3-flash-fullimage")
    if not tool:
        return _missing("pm3-flash-fullimage")
    argv = [tool] + ([port] if port else [])
    return _run(argv, timeout)


def flash_bootrom(port: str | None = None, timeout: float = 300.0) -> FlashResult:
    """Flash hanya bootrom memakai ``pm3-flash-bootrom``.

    Biasanya perlu menahan tombol perangkat saat mencolokkan agar masuk
    mode bootloader.
    """
    tool = _tool("pm3-flash-bootrom")
    if not tool:
        return _missing("pm3-flash-bootrom")
    argv = [tool] + ([port] if port else [])
    return _run(argv, timeout)


def flash_with_flasher(port: str, bootrom: str | None = None,
                       fullimage: str | None = None,
                       timeout: float = 300.0) -> list[FlashResult]:
    """Flash file .elf eksplisit memakai binary ``flasher`` mentah.

    Urutan resmi: bootrom dulu (``-b``), lalu fullimage.
    Minimal salah satu dari ``bootrom``/``fullimage`` harus diberikan.
    """
    if not (bootrom or fullimage):
        raise ValueError("Beri setidaknya satu: bootrom atau fullimage (.elf).")
    tool = _tool("flasher")
    if not tool:
        return [_missing("flasher")]

    results: list[FlashResult] = []
    if bootrom:
        results.append(_run([tool, port, "-b", bootrom], timeout))
    if fullimage:
        results.append(_run([tool, port, fullimage], timeout))
    return results


def _missing(name: str) -> FlashResult:
    return FlashResult(
        command=name,
        stdout="",
        stderr=(f"'{name}' tidak ditemukan di PATH. Install client Proxmark3 "
                "Iceman/RRG, atau build firmware dari source (lihat firmware.py)."),
        returncode=127,
    )
