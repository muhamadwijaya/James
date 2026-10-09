"""Lapisan tipis untuk memanggil client Proxmark3 (`pm3`).

Semua interaksi dengan perangkat keras dilakukan lewat executable `pm3`
resmi, jadi tool ini tidak mengandung firmware atau kode low-level
sendiri — hanya mengotomasi perintah yang biasa Anda ketik manual.
"""

from __future__ import annotations

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
        return shutil.which(self.binary) is not None

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

        joined = "; ".join(commands)
        argv = [self.binary]
        if self.port:
            argv += ["-p", self.port]   # cocok dgn `pm3 -p com10`
        argv += ["-c", joined]

        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout or self.timeout,
        )
        return PM3Result(
            command=joined,
            stdout=proc.stdout,
            stderr=proc.stderr,
            returncode=proc.returncode,
        )
