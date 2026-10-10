"""Output langsung dan pembatalan proses recovery beserta proses anaknya."""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import threading
import time

from .client import PM3Result


def run_process(argv: list[str], command: str, *, timeout: float, cwd: str | None = None,
                env: dict | None = None, emit=None, cancel: threading.Event | None = None) -> PM3Result:
    if cancel and cancel.is_set():
        return PM3Result(command, "", "Dibatalkan sebelum proses dimulai.", 130)
    proc = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, errors="replace", bufsize=1, cwd=cwd, env=env,
        start_new_session=os.name != "nt",
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0)
    messages: queue.Queue[str | None] = queue.Queue()
    chunks: list[str] = []

    def reader() -> None:
        try:
            for line in proc.stdout:
                messages.put(line)
        finally:
            messages.put(None)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    deadline = time.monotonic() + timeout
    stopped = ""
    end = False
    def terminate() -> None:
        if os.name == "nt":
            try:
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                               capture_output=True, timeout=10)
                if proc.poll() is None:
                    proc.kill()
            except (OSError, subprocess.TimeoutExpired):
                if proc.poll() is None:
                    proc.kill()
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    try:
        while not end or proc.poll() is None:
            if not stopped and ((cancel and cancel.is_set()) or time.monotonic() >= deadline):
                stopped = "Dibatalkan oleh pengguna." if cancel and cancel.is_set() else "Batas waktu recovery tercapai."
                terminate()
            if end:
                time.sleep(0.05)
                continue
            try:
                line = messages.get(timeout=0.05)
            except KeyboardInterrupt:
                stopped = "Dibatalkan oleh pengguna."
                terminate()
                continue
            except queue.Empty:
                continue
            if line is None:
                end = True
            else:
                chunks.append(line)
                if emit:
                    emit(line)
    except BaseException:
        terminate()
        proc.wait(timeout=10)
        thread.join(timeout=1)
        proc.stdout.close()
        raise
    proc.wait()
    thread.join(timeout=1)
    proc.stdout.close()
    code = 130 if stopped.startswith("Dibatalkan") else 124 if stopped else proc.returncode
    if stopped and emit:
        emit(stopped + "\n")
    return PM3Result(command, "".join(chunks), stopped, code)
