"""GUI desktop sederhana untuk pm3tool (Tkinter, tanpa dependensi tambahan).

Jalankan dengan:
    python -m pm3tool.gui
atau:
    python -m pm3tool gui

Semua operasi PM3 dijalankan di thread terpisah supaya jendela tidak
membeku saat perintah panjang (mis. hardnested di recover-keys).
"""

from __future__ import annotations

import queue
import os
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from .client import PM3Client, PM3NotFound
from .detection import Connection, detect_connection
from . import scanner


class PM3App:
    def __init__(self, root: tk.Tk, binary: str | None = None,
                 port: str | None = None) -> None:
        self.root = root
        self.root.title("pm3tool — Proxmark3 RFID reader")
        self.root.geometry("820x600")
        self.root.minsize(640, 460)

        self._initial_binary = binary or os.environ.get("PM3_BINARY", "pm3")
        self._initial_port = port or os.environ.get("PM3_PORT", "")
        self._manual_port = bool(self._initial_port)
        self._msg_queue: queue.Queue[tuple[str, str | Connection]] = queue.Queue()
        self._worker: threading.Thread | None = None

        self._build_toolbar()
        self._build_actions()
        self._build_output()
        self._build_statusbar()

        self.root.after(100, self._drain_queue)
        self.root.after(0, self.on_detect)

    # ---------- layout ----------
    def _build_toolbar(self) -> None:
        bar = ttk.Frame(self.root, padding=(8, 8, 8, 0))
        bar.pack(fill=tk.X)

        ttk.Label(bar, text="PM3:").pack(side=tk.LEFT)
        self.binary_var = tk.StringVar(value=self._initial_binary)
        self.binary_entry = ttk.Entry(bar, textvariable=self.binary_var, width=40)
        self.binary_entry.pack(side=tk.LEFT, padx=(2, 10), fill=tk.X, expand=True)

        ttk.Label(bar, text="Port:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value=self._initial_port)
        self.port_entry = ttk.Entry(bar, textvariable=self.port_var, width=10)
        self.port_entry.pack(side=tk.LEFT, padx=(2, 10))
        self.port_entry.bind("<KeyRelease>", self._port_edited)
        self.detect_btn = ttk.Button(bar, text="Auto Detect",
                                     command=lambda: self.on_detect(force=True))
        self.detect_btn.pack(side=tk.LEFT)

    def _port_edited(self, event=None) -> None:
        self._manual_port = bool(self.port_var.get().strip())

    def on_detect(self, force: bool = False) -> None:
        binary = "auto" if force else self.binary_var.get().strip() or "pm3"
        self._detect_binary = "pm3" if force else binary
        port = None if force or not self._manual_port else self.port_var.get().strip()
        self._detect_keep_port = bool(port)

        def job(client) -> None:
            self._msg_queue.put(("__detected__", detect_connection(binary, port)))
        self._run_async("Auto Detect", job)

    def _apply_detection(self, result: Connection) -> None:
        self.binary_var.set(result.binary or self._detect_binary)
        self.port_var.set(result.port or "")
        self._manual_port = self._detect_keep_port
        for message in result.messages:
            self._write(message + "\n", "info")

    def _build_actions(self) -> None:
        frame = ttk.Frame(self.root, padding=8)
        frame.pack(fill=tk.X)

        self.buttons: list[ttk.Button] = []
        actions = [
            ("Check", self.on_check),
            ("Scan (LF+HF)", self.on_scan),
            ("Read HF", self.on_read_hf),
            ("Read LF", self.on_read_lf),
            ("Recover Keys", self.on_recover),
            ("Dump…", self.on_dump),
        ]
        for i, (label, cmd) in enumerate(actions):
            b = ttk.Button(frame, text=label, command=cmd)
            b.grid(row=0, column=i, padx=3, sticky="ew")
            frame.columnconfigure(i, weight=1)
            self.buttons.append(b)

        self.clear_btn = ttk.Button(frame, text="Clear", command=self.clear_output)
        self.clear_btn.grid(row=0, column=len(actions), padx=(12, 3))

    def _build_output(self) -> None:
        frame = ttk.Frame(self.root, padding=(8, 0, 8, 8))
        frame.pack(fill=tk.BOTH, expand=True)

        self.output = tk.Text(frame, wrap=tk.WORD, font=("TkFixedFont", 10),
                              bg="#111418", fg="#d6d9dd", insertbackground="#d6d9dd")
        self.output.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb = ttk.Scrollbar(frame, command=self.output.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.output.config(yscrollcommand=sb.set, state=tk.DISABLED)

        self.output.tag_config("info", foreground="#6ab0ff")
        self.output.tag_config("ok", foreground="#5ad17a")
        self.output.tag_config("err", foreground="#ff6b6b")

    def _build_statusbar(self) -> None:
        self.status = tk.StringVar(value="Siap.")
        bar = ttk.Frame(self.root)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, side=tk.BOTTOM)
        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=120)
        self.progress.pack(side=tk.RIGHT, padx=8, pady=4)
        ttk.Label(bar, textvariable=self.status).pack(side=tk.LEFT, padx=8, pady=4)

    # ---------- helpers ----------
    def _client(self) -> PM3Client:
        port = (self.port_var.get().strip() or None) if self._manual_port else None
        binary = self.binary_var.get().strip() or "pm3"
        return PM3Client(binary=binary, port=port, timeout=600.0)

    def _write(self, text: str, tag: str | None = None) -> None:
        self.output.config(state=tk.NORMAL)
        if tag:
            self.output.insert(tk.END, text, tag)
        else:
            self.output.insert(tk.END, text)
        self.output.see(tk.END)
        self.output.config(state=tk.DISABLED)

    def clear_output(self) -> None:
        self.output.config(state=tk.NORMAL)
        self.output.delete("1.0", tk.END)
        self.output.config(state=tk.DISABLED)

    def _set_busy(self, busy: bool, status: str = "") -> None:
        for b in self.buttons:
            b.config(state=tk.DISABLED if busy else tk.NORMAL)
        for widget in (self.binary_entry, self.port_entry, self.detect_btn):
            widget.config(state=tk.DISABLED if busy else tk.NORMAL)
        if busy:
            self.progress.start(12)
            self.status.set(status or "Menjalankan…")
        else:
            self.progress.stop()
            self.status.set(status or "Siap.")

    def _run_async(self, title: str, func) -> None:
        """Jalankan `func(client)` di thread, hasil dikirim lewat queue."""
        if self._worker and self._worker.is_alive():
            self._msg_queue.put(("err", "Masih ada operasi berjalan.\n"))
            return

        self._msg_queue.put(("info", f"\n=== {title} ===\n"))
        self._set_busy(True, f"{title}…")
        client = self._client()

        def task() -> None:
            try:
                if title != "Auto Detect" and not client.available():
                    raise PM3NotFound(
                        f"Executable '{client.binary}' tidak ditemukan di PATH. "
                        "Install client Proxmark3 Iceman dulu."
                    )
                func(client)
                self._msg_queue.put(("__done_ok__", title))
            except PM3NotFound as exc:
                self._msg_queue.put(("err", f"ERROR: {exc}\n"))
                self._msg_queue.put(("__done_err__", title))
            except Exception as exc:  # noqa: BLE001 - tampilkan apa pun ke user
                self._msg_queue.put(("err", f"ERROR: {exc}\n"))
                self._msg_queue.put(("__done_err__", title))

        self._worker = threading.Thread(target=task, daemon=True)
        self._worker.start()

    def _drain_queue(self) -> None:
        try:
            while True:
                tag, text = self._msg_queue.get_nowait()
                if tag == "__detected__":
                    self._apply_detection(text)
                elif tag == "__done_ok__":
                    self._set_busy(False, f"Selesai: {text}")
                elif tag == "__done_err__":
                    self._set_busy(False, f"Gagal: {text}")
                else:
                    self._write(text, tag if tag in ("info", "ok", "err") else None)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_queue)

    def _emit(self, text: str, tag: str | None = None) -> None:
        self._msg_queue.put((tag or "", text))

    # ---------- actions (berjalan di thread) ----------
    def on_check(self) -> None:
        def job(c: PM3Client) -> None:
            res = scanner.check_device(c)
            self._emit(res.stdout or res.stderr)
        self._run_async("Check device", job)

    def on_scan(self) -> None:
        def job(c: PM3Client) -> None:
            data = scanner.scan_auto(c)
            hf = data["hf"]
            self._emit("HF (13.56 MHz):\n", "info")
            for k in ("uid", "atqa", "sak"):
                if hf.get(k):
                    self._emit(f"  {k.upper():5}: {hf[k]}\n")
            if data["lf_em410x"]:
                self._emit("LF (125 kHz):\n", "info")
                self._emit(f"  EM410x ID: {data['lf_em410x']}\n")
            if not (hf.get("uid") or data["lf_em410x"]):
                self._emit("Tidak ada kartu terdeteksi.\n", "err")
        self._run_async("Scan", job)

    def on_read_hf(self) -> None:
        def job(c: PM3Client) -> None:
            data = scanner.read_hf_14a(c)
            if data.get("uid"):
                for k in ("uid", "atqa", "sak"):
                    if data.get(k):
                        self._emit(f"  {k.upper():5}: {data[k]}\n")
            else:
                self._emit("Tidak ada kartu HF terdeteksi.\n", "err")
                self._emit(data["raw"])
        self._run_async("Read HF", job)

    def on_read_lf(self) -> None:
        def job(c: PM3Client) -> None:
            data = scanner.read_lf_em410x(c)
            if data.get("id"):
                self._emit(f"  EM410x ID: {data['id']}\n", "ok")
            else:
                self._emit("Tidak ada kartu LF terdeteksi.\n", "err")
                self._emit(data["raw"])
        self._run_async("Read LF", job)

    def on_recover(self) -> None:
        self._emit(
            "\nCatatan: recover-keys memakai `hf mf autopwn` (dictionary + "
            "nested/hardnested). Bisa beberapa menit. Jangan lepas kartu dari "
            "antena. Gunakan hanya pada kartu milik sendiri.\n", "info")

        def job(c: PM3Client) -> None:
            data = scanner.recover_mifare_keys(c, timeout=600.0)
            if data["keys"]:
                self._emit("Key ditemukan:\n", "ok")
                self._emit(f"  {'Sektor':>6} | Tipe | Key\n")
                for k in data["keys"]:
                    self._emit(f"  {k['sector']:>6} |  {k['type']}   | {k['key']}\n")
                self._emit("\nDump kartu disimpan oleh client PM3 di direktori kerjanya.\n")
            else:
                self._emit("Belum ada key yang berhasil dipulihkan.\n", "err")
                self._emit(data["raw"])
        self._run_async("Recover keys", job)

    def on_dump(self) -> None:
        keyfile = filedialog.askopenfilename(
            title="Pilih file key (.bin) hasil autopwn — batal untuk pakai key default",
            filetypes=[("Key file", "*.bin"), ("Semua file", "*.*")],
        )

        def job(c: PM3Client) -> None:
            res = scanner.dump_mifare(c, keyfile=keyfile or None)
            self._emit(res.stdout or res.stderr)
        self._run_async("Dump", job)


def main(binary: str | None = None, port: str | None = None) -> int:
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    PM3App(root, binary=binary, port=port)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
