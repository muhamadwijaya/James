"""Starts the C# FTP backend (FtpBackend.exe) and turns its JSON lines into Qt signals."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from app_config import APP_NAME, app_dir

BACKEND_EXE = "FtpBackend.exe" if os.name == "nt" else "FtpBackend"
PASSWORD_ENV = "FTPBRIDGE_PASSWORD"


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _stable_copy(bundled: Path) -> Path:
    """Copy the bundled backend to a fixed folder.

    PyInstaller unpacks into a new random temp folder on every start; running the FTP
    server from there would make Windows Firewall ask for permission every time.
    """
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share")
    target = base / APP_NAME / "bin" / bundled.name
    try:
        if target.exists() and _digest(target) == _digest(bundled):
            return target
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        shutil.copy2(bundled, tmp)
        os.replace(tmp, target)
        return target
    except OSError:
        return bundled


def find_backend() -> Path:
    override = os.environ.get("FTPRENAMER_BACKEND")
    if override and Path(override).is_file():
        return Path(override)

    beside = app_dir() / BACKEND_EXE
    if beside.is_file():
        return beside

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass) / "backend" / BACKEND_EXE
        if bundled.is_file():
            return _stable_copy(bundled)

    dev_build = Path(__file__).resolve().parent.parent / "build" / "backend" / BACKEND_EXE
    if dev_build.is_file():
        return dev_build

    raise FileNotFoundError(
        f"{BACKEND_EXE} tidak ditemukan. Jalankan build.bat terlebih dahulu "
        f"atau letakkan {BACKEND_EXE} di folder yang sama dengan aplikasi."
    )


class BackendClient(QObject):
    event_received = Signal(dict)
    output_text = Signal(str, str)  # level, text (non-JSON output / stderr)
    started = Signal()
    finished = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._proc: QProcess | None = None
        self._buffer = b""

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.state() != QProcess.ProcessState.NotRunning

    def start(self, program: Path, args: list[str], password: str) -> None:
        if self.is_running():
            return
        proc = QProcess(self)
        proc.setProgram(str(program))
        proc.setArguments(args)
        env = QProcessEnvironment.systemEnvironment()
        env.insert(PASSWORD_ENV, password)
        proc.setProcessEnvironment(env)
        proc.setWorkingDirectory(str(program.parent))
        proc.readyReadStandardOutput.connect(self._read_stdout)
        proc.readyReadStandardError.connect(self._read_stderr)
        proc.started.connect(self.started)
        proc.finished.connect(self._on_finished)
        proc.errorOccurred.connect(self._on_error)
        self._buffer = b""
        self._proc = proc
        proc.start()

    def send(self, command: str) -> None:
        if self.is_running():
            self._proc.write((command + "\n").encode("utf-8"))

    def stop(self, kill_after_ms: int = 15000) -> None:
        """Ask the backend to stop; kill it if it does not exit in time."""
        if not self.is_running():
            return
        self.send("STOP")
        proc = self._proc
        QTimer.singleShot(kill_after_ms, lambda: self._kill(proc))

    def stop_blocking(self, timeout_ms: int = 12000) -> None:
        if not self.is_running():
            return
        proc = self._proc
        self.send("STOP")
        if not proc.waitForFinished(timeout_ms):
            proc.kill()
            proc.waitForFinished(2000)

    def _kill(self, proc: QProcess) -> None:
        if proc is self._proc and self.is_running():
            self.output_text.emit("warn", "Backend tidak merespons, proses dihentikan paksa.")
            proc.kill()

    def _read_stdout(self) -> None:
        self._buffer += bytes(self._proc.readAllStandardOutput())
        *lines, self._buffer = self._buffer.split(b"\n")
        for raw in lines:
            text = raw.decode("utf-8", errors="replace").strip()
            if not text:
                continue
            try:
                event = json.loads(text)
            except ValueError:
                self.output_text.emit("info", text)
                continue
            if isinstance(event, dict):
                self.event_received.emit(event)

    def _read_stderr(self) -> None:
        text = bytes(self._proc.readAllStandardError()).decode("utf-8", errors="replace").strip()
        if text:
            self.output_text.emit("error", text)

    def _on_finished(self, exit_code: int, _status) -> None:
        if self._proc is not None:
            self._read_stdout()
            self._proc.deleteLater()
            self._proc = None
        self.finished.emit(exit_code)

    def _on_error(self, error) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            self.output_text.emit("error", "Backend gagal dijalankan: " + (self._proc.errorString() if self._proc else ""))
            if self._proc is not None:
                self._proc.deleteLater()
                self._proc = None
            self.finished.emit(-1)
