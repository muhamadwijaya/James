"""Mendapatkan firmware Proxmark3 resmi (Iceman/RRG).

Firmware Proxmark3 bersifat open-source (GPL). Cara resmi memperolehnya
adalah build dari repo resmi:

    https://github.com/RfidResearchGroup/proxmark3

Modul ini:
  * menemukan file firmware .elf yang sudah ada di sistem, dan
  * (opsional) meng-clone + build repo resmi untuk menghasilkan
    ``bootrom.elf`` dan ``fullimage.elf``.

Build butuh toolchain ARM (arm-none-eabi-gcc) dan dependensi lain sesuai
panduan resmi; modul ini hanya menjalankan ``git``/``make`` resmi, tidak
menyertakan biner firmware apa pun.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field

OFFICIAL_REPO = "https://github.com/RfidResearchGroup/proxmark3.git"

# Lokasi umum file firmware pada instalasi Iceman.
_COMMON_FW_DIRS = [
    "/usr/local/share/proxmark3/firmware",
    "/usr/share/proxmark3/firmware",
    os.path.expanduser("~/proxmark3/armsrc/obj"),
    os.path.expanduser("~/proxmark3/bootrom/obj"),
]


@dataclass
class FirmwareFiles:
    bootrom: str | None = None
    fullimage: str | None = None
    searched: list[str] = field(default_factory=list)

    @property
    def found(self) -> bool:
        return bool(self.bootrom or self.fullimage)


def find_firmware(extra_dirs: list[str] | None = None) -> FirmwareFiles:
    """Cari ``bootrom.elf`` dan ``fullimage.elf`` di lokasi umum."""
    dirs = list(_COMMON_FW_DIRS)
    if extra_dirs:
        dirs = extra_dirs + dirs

    result = FirmwareFiles(searched=dirs)
    for d in dirs:
        if not os.path.isdir(d):
            continue
        boot = os.path.join(d, "bootrom.elf")
        full = os.path.join(d, "fullimage.elf")
        if result.bootrom is None and os.path.isfile(boot):
            result.bootrom = boot
        if result.fullimage is None and os.path.isfile(full):
            result.fullimage = full
    return result


@dataclass
class BuildResult:
    steps: list[tuple[str, int]]  # (deskripsi, returncode)
    log: str
    firmware: FirmwareFiles

    @property
    def ok(self) -> bool:
        return all(code == 0 for _, code in self.steps)


def build_from_source(dest: str, jobs: int | None = None,
                      progress=None, timeout: float = 3600.0) -> BuildResult:
    """Clone repo resmi Iceman ke ``dest`` lalu build firmware.

    Parameters
    ----------
    dest:
        Folder tujuan clone/build (dibuat bila belum ada).
    jobs:
        Jumlah job paralel untuk ``make`` (default: jumlah CPU).
    progress:
        Callback opsional ``progress(teks)`` untuk menampilkan log live.
    """
    if shutil.which("git") is None:
        raise RuntimeError("git tidak ditemukan. Install git dulu.")
    if shutil.which("make") is None:
        raise RuntimeError("make tidak ditemukan. Install build tools dulu.")

    dest = os.path.abspath(dest)
    log_parts: list[str] = []
    steps: list[tuple[str, int]] = []

    def emit(line: str) -> None:
        log_parts.append(line)
        if progress:
            progress(line)

    def run(desc: str, argv: list[str], cwd: str | None = None) -> int:
        emit(f"\n$ {' '.join(argv)}\n")
        proc = subprocess.run(argv, cwd=cwd, capture_output=True,
                              text=True, timeout=timeout)
        emit(proc.stdout)
        if proc.stderr:
            emit(proc.stderr)
        steps.append((desc, proc.returncode))
        return proc.returncode

    if os.path.isdir(os.path.join(dest, ".git")):
        emit(f"Repo sudah ada di {dest}, menarik update…\n")
        run("git pull", ["git", "pull", "--ff-only"], cwd=dest)
    else:
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        if run("git clone", ["git", "clone", "--depth", "1",
                             OFFICIAL_REPO, dest]) != 0:
            return BuildResult(steps, "".join(log_parts), FirmwareFiles())

    njobs = str(jobs or os.cpu_count() or 2)
    # 'make clean' aman diabaikan bila gagal; yang penting 'make'.
    run("make clean", ["make", "clean"], cwd=dest)
    run("make", ["make", f"-j{njobs}"], cwd=dest)

    fw = find_firmware(extra_dirs=[
        os.path.join(dest, "armsrc", "obj"),
        os.path.join(dest, "bootrom", "obj"),
    ])
    return BuildResult(steps, "".join(log_parts), fw)
