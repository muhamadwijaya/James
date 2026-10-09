"""GUI desktop pm3tool berbasis PySide6 (Qt).

Menu:
  * Tab Reader   : Check / Scan / Read HF / Read LF / Recover Keys / Dump
  * Tab Firmware : temukan firmware, flash (all/fullimage/bootrom/custom .elf),
                   dan download+build firmware resmi Iceman dari source.

Jalankan:
    python -m pm3tool gui
    python -m pm3tool.gui_qt

Semua operasi PM3 (baca kartu, flash, build) berjalan di thread Qt
terpisah agar jendela tetap responsif.
"""

from __future__ import annotations

import sys

from PySide6 import QtCore, QtGui, QtWidgets

from .client import PM3Client, PM3NotFound
from . import scanner, flasher, firmware, clone, attack, dumpview


class Worker(QtCore.QThread):
    """Jalankan satu fungsi blocking di thread, kirim output lewat sinyal."""

    line = QtCore.Signal(str, str)   # (teks, tag)
    done = QtCore.Signal(bool, str)  # (sukses, judul)

    def __init__(self, title: str, fn) -> None:
        super().__init__()
        self._title = title
        self._fn = fn

    def run(self) -> None:  # noqa: D401 - dipanggil Qt
        def emit(text: str, tag: str = "") -> None:
            self.line.emit(text, tag)
        try:
            self._fn(emit)
            self.done.emit(True, self._title)
        except PM3NotFound as exc:
            self.line.emit(f"ERROR: {exc}\n", "err")
            self.done.emit(False, self._title)
        except Exception as exc:  # noqa: BLE001
            self.line.emit(f"ERROR: {exc}\n", "err")
            self.done.emit(False, self._title)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("pm3tool — Proxmark3 RFID + Firmware")
        self.resize(900, 640)
        self._worker: Worker | None = None

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QVBoxLayout(central)

        root.addLayout(self._build_connbar())

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self._build_reader_tab(), "Reader")
        self.tabs.addTab(self._build_viewer_tab(), "Dump Viewer")
        self.tabs.addTab(self._build_clone_tab(), "Clone")
        self.tabs.addTab(self._build_firmware_tab(), "Firmware")
        root.addWidget(self.tabs, 1)

        self.output = QtWidgets.QPlainTextEdit(readOnly=True)
        self.output.setFont(QtGui.QFont("Monospace", 10))
        self.output.setStyleSheet(
            "QPlainTextEdit{background:#111418;color:#d6d9dd;}")
        root.addWidget(self.output, 2)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress)
        self.statusBar().showMessage("Siap.")

    # ---------- bagian atas ----------
    def _build_connbar(self) -> QtWidgets.QHBoxLayout:
        bar = QtWidgets.QHBoxLayout()
        bar.addWidget(QtWidgets.QLabel("Binary:"))
        self.binary_edit = QtWidgets.QLineEdit("pm3")
        self.binary_edit.setMaximumWidth(180)
        self.binary_edit.setToolTip(
            "Path ke client Proxmark3 (pm3 / pm3.bat / pm3.exe). "
            "Pakai 'pm3' jika sudah di PATH, atau Browse ke lokasinya.")
        bar.addWidget(self.binary_edit)
        browse = QtWidgets.QPushButton("Browse…")
        browse.setToolTip("Pilih file pm3 / pm3.bat / pm3.exe dari ProxSpace.")
        browse.clicked.connect(self._pick_binary)
        bar.addWidget(browse)

        bar.addWidget(QtWidgets.QLabel("Port:"))
        self.port_edit = QtWidgets.QLineEdit()
        self.port_edit.setPlaceholderText("kosong = auto (mis. COM3 / /dev/ttyACM0)")
        bar.addWidget(self.port_edit, 1)

        clear = QtWidgets.QPushButton("Clear log")
        clear.clicked.connect(self.output_clear)
        bar.addWidget(clear)
        return bar

    def _pick_binary(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Pilih client Proxmark3 (pm3 / pm3.bat / pm3.exe)", "",
            "Proxmark3 client (pm3 pm3.bat pm3.exe);;Semua file (*.*)")
        if path:
            self.binary_edit.setText(path)

    # ---------- tab Reader ----------
    def _build_reader_tab(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        self.reader_buttons: list[QtWidgets.QPushButton] = []

        grid = QtWidgets.QGridLayout()
        actions = [
            ("Check device", self.on_check),
            ("Scan (LF+HF)", self.on_scan),
            ("Read HF", self.on_read_hf),
            ("Read LF", self.on_read_lf),
            ("Recover Keys (dari kartu)", self.on_recover),
            ("Dump…", self.on_dump),
        ]
        for i, (label, cb) in enumerate(actions):
            b = QtWidgets.QPushButton(label)
            b.clicked.connect(cb)
            grid.addWidget(b, i // 3, i % 3)
            self.reader_buttons.append(b)
        lay.addLayout(grid)

        # --- pemulihan key lewat READER (mfkey32 / sniff) ---
        box = QtWidgets.QGroupBox("Recover key lewat READER (punya reader-nya)")
        gl = QtWidgets.QVBoxLayout(box)
        gl.addWidget(QtWidgets.QLabel(
            "Pakai ini kalau reader masih tahu key-nya. Key tidak pernah "
            "dikirim reader, tapi bisa DIHITUNG dari autentikasinya."))

        urow = QtWidgets.QHBoxLayout()
        urow.addWidget(QtWidgets.QLabel("UID (untuk simulasi):"))
        self.sim_uid_edit = QtWidgets.QLineEdit()
        self.sim_uid_edit.setPlaceholderText("mis. 2CD72F90 (kosong = default)")
        urow.addWidget(self.sim_uid_edit, 1)
        gl.addLayout(urow)

        b_reader = QtWidgets.QPushButton(
            "Recover via Reader — PM3 jadi kartu, tempel ke reader (mfkey32)")
        b_reader.clicked.connect(self.on_recover_reader)
        gl.addWidget(b_reader)

        b_sniff = QtWidgets.QPushButton(
            "Sniff & Crack — sadap reader↔kartu, lalu pecahkan (trace)")
        b_sniff.clicked.connect(self.on_sniff_crack)
        gl.addWidget(b_sniff)
        self.reader_buttons += [b_reader, b_sniff]

        lay.addWidget(box)
        lay.addStretch(1)
        return w

    # ---------- tab Dump Viewer ----------
    def _build_viewer_tab(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        lay.addWidget(QtWidgets.QLabel(
            "Lihat isi dump (.bin/.eml/.json) dalam hex / ASCII. "
            "Isi sektor 1–4 ditampilkan apa adanya untuk dibandingkan."))

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Dump:"))
        self.view_dump_edit = QtWidgets.QLineEdit()
        row.addWidget(self.view_dump_edit, 1)
        pick = QtWidgets.QPushButton("Pilih…")
        pick.clicked.connect(lambda: self._pick_into(
            self.view_dump_edit, "Dump (*.bin *.eml *.json);;Semua file (*.*)"))
        row.addWidget(pick)
        lay.addLayout(row)

        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(QtWidgets.QLabel("Sektor:"))
        self.view_sectors_edit = QtWidgets.QLineEdit()
        self.view_sectors_edit.setPlaceholderText("mis. 1-4 (kosong = semua)")
        self.view_sectors_edit.setMaximumWidth(160)
        row2.addWidget(self.view_sectors_edit)
        row2.addWidget(QtWidgets.QLabel("Format:"))
        self.view_format = QtWidgets.QComboBox()
        self.view_format.addItems(["Hex + ASCII", "Hex", "ASCII"])
        row2.addWidget(self.view_format)
        show = QtWidgets.QPushButton("Tampilkan")
        show.clicked.connect(self.on_view_dump)
        row2.addWidget(show)
        row2.addStretch(1)
        lay.addLayout(row2)

        self.view_out = QtWidgets.QPlainTextEdit(readOnly=True)
        self.view_out.setFont(QtGui.QFont("Monospace", 9))
        self.view_out.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        self.view_out.setStyleSheet(
            "QPlainTextEdit{background:#0c0f12;color:#cfe8d0;}")
        lay.addWidget(self.view_out, 1)
        return w

    def on_view_dump(self) -> None:
        path = self.view_dump_edit.text().strip()
        if not path:
            self.view_out.setPlainText("Pilih file dump dulu.")
            return
        mode = {"Hex + ASCII": "both", "Hex": "hex",
                "ASCII": "ascii"}[self.view_format.currentText()]
        sectors = self.view_sectors_edit.text().strip() or None
        try:
            text = dumpview.view_file(path, sectors_arg=sectors, mode=mode)
        except (OSError, ValueError) as exc:
            text = f"ERROR: {exc}"
        self.view_out.setPlainText(text)

    # ---------- tab Clone ----------
    def _build_clone_tab(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)
        self.clone_buttons: list[QtWidgets.QPushButton] = []

        info = QtWidgets.QLabel(
            "Pindahkan isi kartu ke chip baru.\n"
            "Langkah: (1) di tab Reader, Recover Keys → menghasilkan file dump "
            ".bin + key. (2) tempel chip BARU. (3) tulis dump ke chip baru di sini.\n"
            "Untuk UID yang sama, chip baru harus kartu MAGIC (Gen1a/Gen2/Gen3)."
        )
        info.setWordWrap(True)
        lay.addWidget(info)

        # deteksi magic
        row = QtWidgets.QHBoxLayout()
        b_info = QtWidgets.QPushButton("Deteksi kartu magic (hf mf info)")
        b_info.clicked.connect(self.on_clone_info)
        row.addWidget(b_info)
        b_wipe = QtWidgets.QPushButton("Wipe Gen1a (kosongkan)")
        b_wipe.clicked.connect(self.on_clone_wipe)
        row.addWidget(b_wipe)
        self.clone_buttons += [b_info, b_wipe]
        lay.addLayout(row)

        # file dump
        box = QtWidgets.QGroupBox("File dump sumber (.bin/.eml/.json dari Recover Keys)")
        g = QtWidgets.QGridLayout(box)
        self.dump_edit = QtWidgets.QLineEdit()
        g.addWidget(QtWidgets.QLabel("Dump:"), 0, 0)
        g.addWidget(self.dump_edit, 0, 1)
        pick_dump = QtWidgets.QPushButton("Pilih…")
        pick_dump.clicked.connect(lambda: self._pick_into(
            self.dump_edit, "Dump (*.bin *.eml *.json);;Semua file (*.*)"))
        g.addWidget(pick_dump, 0, 2)
        self.key_edit = QtWidgets.QLineEdit()
        g.addWidget(QtWidgets.QLabel("Key file:"), 1, 0)
        g.addWidget(self.key_edit, 1, 1)
        pick_key = QtWidgets.QPushButton("Pilih…")
        pick_key.clicked.connect(lambda: self._pick_into(
            self.key_edit, "Key (*.bin);;Semua file (*.*)"))
        g.addWidget(pick_key, 1, 2)
        lay.addWidget(box)

        # aksi tulis
        box2 = QtWidgets.QGroupBox("Tulis ke chip baru")
        g2 = QtWidgets.QVBoxLayout(box2)

        b_gen1a = QtWidgets.QPushButton(
            "Clone ke MAGIC Gen1a — semua blok + UID (hf mf cload)")
        b_gen1a.clicked.connect(self.on_clone_gen1a)
        g2.addWidget(b_gen1a)

        self.wb0_check = QtWidgets.QCheckBox(
            "Ikut tulis blok 0 / UID (butuh kartu Gen2/CUID yang mendukung)")
        g2.addWidget(self.wb0_check)
        b_restore = QtWidgets.QPushButton(
            "Restore pakai key — kartu normal / Gen2 (hf mf restore)")
        b_restore.clicked.connect(self.on_clone_restore)
        g2.addWidget(b_restore)

        b_verify = QtWidgets.QPushButton("Verifikasi isi kartu magic (hf mf cview)")
        b_verify.clicked.connect(self.on_clone_verify)
        g2.addWidget(b_verify)
        lay.addWidget(box2)
        self.clone_buttons += [b_gen1a, b_restore, b_verify]

        # set UID
        box3 = QtWidgets.QGroupBox("Set UID kartu magic Gen1a")
        g3 = QtWidgets.QHBoxLayout(box3)
        self.uid_edit = QtWidgets.QLineEdit()
        self.uid_edit.setPlaceholderText("hex tanpa pemisah, mis. 2CD72F90")
        g3.addWidget(self.uid_edit, 1)
        b_uid = QtWidgets.QPushButton("Set UID")
        b_uid.clicked.connect(self.on_clone_set_uid)
        g3.addWidget(b_uid)
        self.clone_buttons.append(b_uid)
        lay.addWidget(box3)

        lay.addStretch(1)
        return w

    # ---------- tab Firmware ----------
    def _build_firmware_tab(self) -> QtWidgets.QWidget:
        w = QtWidgets.QWidget()
        lay = QtWidgets.QVBoxLayout(w)

        info = QtWidgets.QLabel(
            "Flash firmware Proxmark3 memakai tool resmi Iceman/RRG.\n"
            "Flash hanya perangkat milik Anda sendiri. Jangan cabut saat proses berjalan."
        )
        info.setWordWrap(True)
        lay.addWidget(info)

        # baris flash cepat
        row1 = QtWidgets.QHBoxLayout()
        self.fw_buttons: list[QtWidgets.QPushButton] = []
        for label, cb in [
            ("Temukan firmware", self.on_find_fw),
            ("Flash ALL (bootrom+image)", self.on_flash_all),
            ("Flash fullimage", self.on_flash_full),
            ("Flash bootrom", self.on_flash_boot),
        ]:
            b = QtWidgets.QPushButton(label)
            b.clicked.connect(cb)
            row1.addWidget(b)
            self.fw_buttons.append(b)
        lay.addLayout(row1)

        # flash custom .elf
        box = QtWidgets.QGroupBox("Flash file .elf kustom (flasher mentah)")
        g = QtWidgets.QGridLayout(box)
        self.boot_edit = QtWidgets.QLineEdit()
        self.full_edit = QtWidgets.QLineEdit()
        g.addWidget(QtWidgets.QLabel("bootrom.elf:"), 0, 0)
        g.addWidget(self.boot_edit, 0, 1)
        bb = QtWidgets.QPushButton("Pilih…")
        bb.clicked.connect(lambda: self._pick_into(self.boot_edit))
        g.addWidget(bb, 0, 2)
        g.addWidget(QtWidgets.QLabel("fullimage.elf:"), 1, 0)
        g.addWidget(self.full_edit, 1, 1)
        fb = QtWidgets.QPushButton("Pilih…")
        fb.clicked.connect(lambda: self._pick_into(self.full_edit))
        g.addWidget(fb, 1, 2)
        flash_custom = QtWidgets.QPushButton("Flash file .elf di atas")
        flash_custom.clicked.connect(self.on_flash_custom)
        g.addWidget(flash_custom, 2, 0, 1, 3)
        self.fw_buttons.append(flash_custom)
        lay.addWidget(box)

        # build dari source
        box2 = QtWidgets.QGroupBox("Dapatkan firmware (build dari source resmi Iceman)")
        g2 = QtWidgets.QVBoxLayout(box2)
        g2.addWidget(QtWidgets.QLabel(
            "Clone github.com/RfidResearchGroup/proxmark3 lalu 'make'.\n"
            "Butuh git, make, dan toolchain ARM (arm-none-eabi-gcc)."))
        build_btn = QtWidgets.QPushButton("Download & build firmware…")
        build_btn.clicked.connect(self.on_build_fw)
        self.fw_buttons.append(build_btn)
        g2.addWidget(build_btn)
        lay.addWidget(box2)

        lay.addStretch(1)
        return w

    # ---------- util ----------
    def _client(self) -> PM3Client:
        port = self.port_edit.text().strip() or None
        binary = self.binary_edit.text().strip() or "pm3"
        return PM3Client(binary=binary, port=port, timeout=600.0)

    def _port(self) -> str | None:
        return self.port_edit.text().strip() or None

    def _pick_into(self, edit: QtWidgets.QLineEdit,
                   filt: str = "ELF (*.elf);;Semua file (*.*)") -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Pilih file", "", filt)
        if path:
            edit.setText(path)

    def output_clear(self) -> None:
        self.output.clear()

    @QtCore.Slot(str, str)
    def _append(self, text: str, tag: str = "") -> None:
        color = {"info": "#6ab0ff", "ok": "#5ad17a", "err": "#ff6b6b"}.get(tag)
        if color:
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            self.output.appendHtml(
                f'<span style="color:{color};white-space:pre">{text}</span>')
        else:
            self.output.moveCursor(QtGui.QTextCursor.End)
            self.output.insertPlainText(text)
        self.output.moveCursor(QtGui.QTextCursor.End)

    def _set_busy(self, busy: bool, msg: str = "") -> None:
        for b in self.reader_buttons + self.clone_buttons + self.fw_buttons:
            b.setEnabled(not busy)
        self.progress.setVisible(busy)
        self.statusBar().showMessage(msg or ("Menjalankan…" if busy else "Siap."))

    def _start(self, title: str, fn) -> None:
        if self._worker and self._worker.isRunning():
            self._append("Masih ada operasi berjalan.\n", "err")
            return
        self._append(f"\n=== {title} ===\n", "info")
        self._set_busy(True, f"{title}…")
        self._worker = Worker(title, fn)
        self._worker.line.connect(self._append)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    @QtCore.Slot(bool, str)
    def _on_done(self, ok: bool, title: str) -> None:
        self._set_busy(False, f"{'Selesai' if ok else 'Gagal'}: {title}")

    def _guard_client(self, emit, client: PM3Client) -> None:
        if not client.available():
            raise PM3NotFound(
                f"Client Proxmark3 '{client.binary}' tidak ditemukan.\n"
                "COM port terdeteksi TIDAK cukup — Anda perlu program client "
                "'pm3' (pm3.exe/pm3.bat).\n"
                "Di Windows: pasang lewat ProxSpace "
                "(github.com/Gator96100/ProxSpace), lalu klik 'Browse…' di "
                "sebelah kolom Binary dan arahkan ke pm3.bat/pm3.exe.")

    # ---------- aksi Reader ----------
    def on_check(self) -> None:
        def job(emit):
            c = self._client(); self._guard_client(emit, c)
            res = scanner.check_device(c)
            emit(res.stdout or res.stderr)
        self._start("Check device", job)

    def on_scan(self) -> None:
        def job(emit):
            c = self._client(); self._guard_client(emit, c)
            data = scanner.scan_auto(c)
            hf = data["hf"]
            emit("HF (13.56 MHz):\n", "info")
            for k in ("uid", "atqa", "sak"):
                if hf.get(k):
                    emit(f"  {k.upper():5}: {hf[k]}\n")
            if data["lf_em410x"]:
                emit("LF (125 kHz):\n", "info")
                emit(f"  EM410x ID: {data['lf_em410x']}\n")
            if not (hf.get("uid") or data["lf_em410x"]):
                emit("Tidak ada kartu terdeteksi.\n", "err")
        self._start("Scan", job)

    def on_read_hf(self) -> None:
        def job(emit):
            c = self._client(); self._guard_client(emit, c)
            data = scanner.read_hf_14a(c)
            if data.get("uid"):
                for k in ("uid", "atqa", "sak"):
                    if data.get(k):
                        emit(f"  {k.upper():5}: {data[k]}\n", "ok")
            else:
                emit("Tidak ada kartu HF terdeteksi.\n", "err")
                emit(data["raw"])
        self._start("Read HF", job)

    def on_read_lf(self) -> None:
        def job(emit):
            c = self._client(); self._guard_client(emit, c)
            data = scanner.read_lf_em410x(c)
            if data.get("id"):
                emit(f"  EM410x ID: {data['id']}\n", "ok")
            else:
                emit("Tidak ada kartu LF terdeteksi.\n", "err")
                emit(data["raw"])
        self._start("Read LF", job)

    def on_recover(self) -> None:
        self._append(
            "Catatan: memakai `hf mf autopwn` (dictionary + nested/hardnested). "
            "Bisa beberapa menit. Gunakan hanya pada kartu milik sendiri.\n", "info")

        def job(emit):
            c = self._client(); self._guard_client(emit, c)
            data = scanner.recover_mifare_keys(c, timeout=600.0)
            if data["keys"]:
                emit("Key ditemukan:\n", "ok")
                emit(f"  {'Sektor':>6} | Tipe | Key\n")
                for k in data["keys"]:
                    emit(f"  {k['sector']:>6} |  {k['type']}   | {k['key']}\n")
                emit("\nDump kartu disimpan client PM3 di direktori kerjanya.\n")
            else:
                emit("Belum ada key yang berhasil dipulihkan.\n", "err")
                emit(data["raw"])
        self._start("Recover keys", job)

    def on_dump(self) -> None:
        keyfile, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Pilih key file (.bin) — batal = key default", "",
            "Key file (*.bin);;Semua file (*.*)")

        def job(emit):
            c = self._client(); self._guard_client(emit, c)
            res = scanner.dump_mifare(c, keyfile=keyfile or None)
            emit(res.stdout or res.stderr)
        self._start("Dump", job)

    def _show_mfkeys(self, emit, keys: list[str]) -> None:
        if keys:
            emit("Key ditemukan:\n", "ok")
            for k in keys:
                emit(f"  {k}\n", "ok")
            emit("Pakai key ini untuk dump/clone (tab Clone atau 'Dump').\n")
        else:
            emit("Belum ada key yang terpulihkan.\n", "err")

    def on_recover_reader(self) -> None:
        uid = self.sim_uid_edit.text().strip() or None
        self._append(
            "PM3 akan menyamar sebagai kartu. TEMPELKAN PM3 ke reader Anda "
            "beberapa kali hingga key ditemukan. Tekan tombol PM3 untuk berhenti.\n",
            "info")

        def job(emit):
            c = self._client(); self._guard_client(emit, c)
            data = attack.recover_via_reader(c, uid=uid, timeout=240.0)
            self._show_mfkeys(emit, data["keys"])
            if not data["keys"]:
                emit("\n" + data["raw"])
        self._start("Recover via Reader", job)

    def on_sniff_crack(self) -> None:
        self._append(
            "Mulai menyadap. Dekatkan kartu asli ke reader agar transaksi "
            "terekam, lalu tekan tombol PM3 untuk mengakhiri sniff.\n", "info")

        def job(emit):
            c = self._client(); self._guard_client(emit, c)
            data = attack.sniff_and_crack(c, sniff_timeout=240.0)
            self._show_mfkeys(emit, data["keys"])
            if not data["keys"]:
                emit("\n--- trace ---\n" + data["raw"])
        self._start("Sniff & Crack", job)

    # ---------- aksi Clone ----------
    def on_clone_info(self) -> None:
        def job(emit):
            c = self._client(); self._guard_client(emit, c)
            data = clone.card_info(c)
            if data["magic"]:
                emit(f"Kartu MAGIC terdeteksi: {', '.join(data['generations'])}\n", "ok")
                emit("Bisa dipakai untuk clone UID yang sama.\n", "ok")
            else:
                emit("Bukan kartu magic (atau tidak terdeteksi).\n", "err")
                emit("Kartu MIFARE Classic biasa TIDAK bisa mengubah UID. "
                     "Isi data tetap bisa ditulis via Restore, tapi UID tetap bawaan.\n")
            emit("\n" + data["raw"])
        self._start("Deteksi magic", job)

    def on_clone_wipe(self) -> None:
        if not self._confirm("Wipe kartu magic Gen1a ke kondisi kosong?"):
            return

        def job(emit):
            c = self._client(); self._guard_client(emit, c)
            res = clone.wipe_gen1a(c)
            emit(res.stdout or res.stderr, "" if res.ok else "err")
        self._start("Wipe Gen1a", job)

    def _dump_path(self) -> str | None:
        return self.dump_edit.text().strip() or None

    def on_clone_gen1a(self) -> None:
        dump = self._dump_path()
        if not dump:
            self._append("Pilih file dump sumber dulu.\n", "err")
            return
        if not self._confirm(
                "Tulis SELURUH dump (termasuk UID) ke kartu magic Gen1a?\n"
                "Tempelkan CHIP BARU (magic) di antena."):
            return

        def job(emit):
            c = self._client(); self._guard_client(emit, c)
            res = clone.clone_to_gen1a(c, dump)
            emit(res.stdout or res.stderr, "" if res.ok else "err")
        self._start("Clone ke Gen1a", job)

    def on_clone_restore(self) -> None:
        dump = self._dump_path()
        key = self.key_edit.text().strip() or None
        wb0 = self.wb0_check.isChecked()
        if not self._confirm(
                "Tulis data dump ke kartu memakai key?\n"
                "Tempelkan CHIP BARU di antena."
                + ("\n(Termasuk blok 0/UID — hanya berhasil di Gen2/CUID.)"
                   if wb0 else "")):
            return

        def job(emit):
            c = self._client(); self._guard_client(emit, c)
            res = clone.restore_dump(c, dumpfile=dump, keyfile=key, write_block0=wb0)
            emit(res.stdout or res.stderr, "" if res.ok else "err")
        self._start("Restore dump", job)

    def on_clone_verify(self) -> None:
        def job(emit):
            c = self._client(); self._guard_client(emit, c)
            data = clone.verify_clone(c, self._dump_path() or "")
            emit(data["raw"], "" if data["ok"] else "err")
        self._start("Verifikasi", job)

    def on_clone_set_uid(self) -> None:
        uid = self.uid_edit.text().strip()
        if not uid:
            self._append("Isi UID dulu (hex, mis. 2CD72F90).\n", "err")
            return
        if not self._confirm(f"Set UID kartu magic Gen1a menjadi {uid}?"):
            return

        def job(emit):
            c = self._client(); self._guard_client(emit, c)
            res = clone.set_magic_uid(c, uid)
            emit(res.stdout or res.stderr, "" if res.ok else "err")
        self._start("Set UID", job)

    # ---------- aksi Firmware ----------
    def on_find_fw(self) -> None:
        def job(emit):
            fw = firmware.find_firmware()
            emit("Lokasi dicek:\n")
            for d in fw.searched:
                emit(f"  - {d}\n")
            if fw.found:
                emit("\nDitemukan:\n", "ok")
                if fw.bootrom:
                    emit(f"  bootrom  : {fw.bootrom}\n", "ok")
                    self.boot_edit.setText(fw.bootrom)
                if fw.fullimage:
                    emit(f"  fullimage: {fw.fullimage}\n", "ok")
                    self.full_edit.setText(fw.fullimage)
            else:
                emit("\nTidak ada firmware .elf ditemukan. Build dari source "
                     "atau tunjukkan path-nya manual.\n", "err")
        self._start("Temukan firmware", job)

    def _confirm(self, text: str) -> bool:
        r = QtWidgets.QMessageBox.question(
            self, "Konfirmasi", text,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        return r == QtWidgets.QMessageBox.Yes

    def _confirm_flash(self, what: str) -> bool:
        r = QtWidgets.QMessageBox.question(
            self, "Konfirmasi flash",
            f"Flash {what} ke perangkat Proxmark3?\n\n"
            "Pastikan perangkat milik Anda terhubung dan jangan dicabut "
            "selama proses. Lanjutkan?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        return r == QtWidgets.QMessageBox.Yes

    def on_flash_all(self) -> None:
        if not self._confirm_flash("bootrom + fullimage (pm3-flash-all)"):
            return
        port = self._port()

        def job(emit):
            res = flasher.flash_all(port=port)
            emit(res.stdout or res.stderr, "" if res.ok else "err")
        self._start("Flash ALL", job)

    def on_flash_full(self) -> None:
        if not self._confirm_flash("fullimage (pm3-flash-fullimage)"):
            return
        port = self._port()

        def job(emit):
            res = flasher.flash_fullimage(port=port)
            emit(res.stdout or res.stderr, "" if res.ok else "err")
        self._start("Flash fullimage", job)

    def on_flash_boot(self) -> None:
        if not self._confirm_flash("bootrom (pm3-flash-bootrom)"):
            return
        port = self._port()

        def job(emit):
            emit("Jika gagal masuk bootloader, tahan tombol saat mencolok "
                 "perangkat, lalu ulangi.\n")
            res = flasher.flash_bootrom(port=port)
            emit(res.stdout or res.stderr, "" if res.ok else "err")
        self._start("Flash bootrom", job)

    def on_flash_custom(self) -> None:
        boot = self.boot_edit.text().strip() or None
        full = self.full_edit.text().strip() or None
        port = self._port()
        if not (boot or full):
            self._append("Isi minimal satu path .elf (bootrom/fullimage).\n", "err")
            return
        if not port:
            self._append("Flasher mentah butuh port eksplisit (isi kolom Port).\n", "err")
            return
        if not self._confirm_flash("file .elf kustom"):
            return

        def job(emit):
            for res in flasher.flash_with_flasher(port, bootrom=boot, fullimage=full):
                emit(res.stdout or res.stderr, "" if res.ok else "err")
        self._start("Flash custom .elf", job)

    def on_build_fw(self) -> None:
        dest = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Pilih folder tujuan clone/build firmware")
        if not dest:
            return

        def job(emit):
            emit("Mulai clone + build firmware resmi Iceman…\n", "info")
            res = firmware.build_from_source(
                dest, progress=lambda s: emit(s))
            if res.ok and res.firmware.found:
                emit("\nBuild selesai.\n", "ok")
                if res.firmware.bootrom:
                    emit(f"  bootrom  : {res.firmware.bootrom}\n", "ok")
                    self.boot_edit.setText(res.firmware.bootrom)
                if res.firmware.fullimage:
                    emit(f"  fullimage: {res.firmware.fullimage}\n", "ok")
                    self.full_edit.setText(res.firmware.fullimage)
            else:
                emit("\nBuild gagal atau firmware tidak ditemukan. "
                     "Cek apakah toolchain ARM terpasang.\n", "err")
        self._start("Build firmware", job)


def main() -> int:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
