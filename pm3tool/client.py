"""Lapisan tipis untuk memanggil client Proxmark3 (`pm3`).

Semua interaksi dengan perangkat keras dilakukan lewat executable `pm3`
resmi, jadi tool ini tidak mengandung firmware atau kode low-level
sendiri — hanya mengotomasi perintah yang biasa Anda ketik manual.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


class PM3NotFound(RuntimeError):
    """Executable `pm3` tidak ditemukan di PATH."""


@dataclass
class PM3Result:
    command: str
    stdout: str
    stderr: str
    returncode: int

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class PM3Client:
    """Menjalankan perintah pada client Proxmark3.

    Parameters
    ----------
    binary:
        Nama/path executable client (default: ``pm3``).
    port:
        Port serial perangkat, mis. ``/dev/ttyACM0`` atau ``COM3``.
        Kosongkan untuk auto-detect (``pm3`` tanpa argumen port).
    timeout:
        Batas waktu (detik) tiap perintah.
    """

    def __init__(self, binary: str = "pm3", port: str | None = None,
                 timeout: float = 30.0) -> None:
        self.binary = binary
        self.port = port
        self.timeout = timeout

    def available(self) -> bool:
        # bisa berupa path lengkap (mis. proxmark3.exe) atau nama di PATH
        if os.path.isfile(self.binary):
            return True
        return shutil.which(self.binary) is not None

    def _is_wrapper(self) -> bool:
        """True jika binary adalah launcher `pm3`/`pm3.bat`, bukan exe mentah.

        Launcher `pm3` memakai flag `-p <port>`; client mentah
        `proxmark3(.exe)` memakai port sebagai argumen posisional.
        """
        exe = os.path.basename(self.binary).lower()
        return exe == "pm3" or exe.startswith("pm3.")

    def _build_argv(self, commands: tuple[str, ...]) -> tuple[list[str], str]:
        joined = "; ".join(commands)
        argv = [self.binary]
        if self.port:
            argv += (["-p", self.port] if self._is_wrapper() else [self.port])
        argv += ["-c", joined]
        return argv, joined

    def _find_mingw_bin(self) -> str | None:
        """Cari folder DLL MinGW (msys2/mingw64/bin) relatif ke binary.

        Agar `proxmark3.exe` hasil ProxSpace bisa jalan di Windows biasa.
        """
        if not os.path.isfile(self.binary):
            return None
        d = os.path.dirname(os.path.abspath(self.binary))
        for _ in range(7):
            cand = os.path.join(d, "msys2", "mingw64", "bin")
            if os.path.isdir(cand):
                return cand
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
        return None

    def _augmented_env(self) -> dict:
        env = os.environ.copy()
        extra: list[str] = []
        manual = os.environ.get("PM3_PATH_ADD")
        if manual:
            extra.append(manual)
        auto = self._find_mingw_bin()
        if auto and auto not in extra:
            extra.append(auto)
        if extra:
            env["PATH"] = os.pathsep.join(extra) + os.pathsep + env.get("PATH", "")
        return env

    def run(self, *commands: str, timeout: float | None = None) -> PM3Result:
        """Jalankan satu atau beberapa perintah client PM3 lalu keluar.

        Beberapa perintah digabung dengan ``;`` persis seperti saat
        diketik manual di dalam client.
        """
        if not self.available():
            raise PM3NotFound(
                f"Executable '{self.binary}' tidak ditemukan. "
                "Install/compile Proxmark3 Iceman dan pastikan ada di PATH."
            )

        argv, joined = self._build_argv(commands)

        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout or self.timeout,
            env=self._augmented_env(),
        )
        return PM3Result(
            command=joined,
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )
