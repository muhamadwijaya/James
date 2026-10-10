"""Pusat recovery: metode PM3, script, dan tool nonce offline."""

from __future__ import annotations

import os
import threading
import time

from PySide6 import QtCore, QtWidgets

from . import recovery


class RecoveryPanel(QtWidgets.QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.cancel_event: threading.Event | None = None
        self.methods = dict(recovery.BY_ID)
        self.controls = []
        self._manual_command = False
        self._auto_output = os.path.abspath("recovery_sessions")
        self._started_at = None
        self.last_report = None
        self._is_recovery = False
        self._operation_title = None
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_elapsed)
        outer = QtWidgets.QVBoxLayout(self)
        instructions = QtWidgets.QLabel(
            "Tempelkan kartu pada antena PM3, klik Recover otomatis, lalu tunggu hasilnya. "
            "PM3 dan COM dideteksi otomatis; serangan dipilih oleh Autopwn.")
        instructions.setWordWrap(True)
        outer.addWidget(instructions)
        primary = QtWidgets.QHBoxLayout()
        self.auto_button = QtWidgets.QPushButton("Recover otomatis")
        self.auto_button.setMinimumHeight(36)
        self.auto_button.clicked.connect(self.run_auto)
        primary.addWidget(self.auto_button, 1)
        self.controls.append(self.auto_button)
        self.stop = QtWidgets.QPushButton("Hentikan")
        self.stop.clicked.connect(self.cancel)
        self.stop.setToolTip("Hentikan proses client. Untuk simulasi/sniff, tekan tombol PM3 bila diperlukan.")
        self.stop.setEnabled(False)
        primary.addWidget(self.stop)
        outer.addLayout(primary)
        self.summary = QtWidgets.QLabel(
            "Siap. Recovery otomatis tidak memerlukan isian parameter.")
        self.summary.setWordWrap(True)
        outer.addWidget(self.summary)
        self.advanced_toggle = QtWidgets.QCheckBox("Metode lanjutan (opsional)")
        self.controls.append(self.advanced_toggle)
        outer.addWidget(self.advanced_toggle)
        self.advanced = QtWidgets.QWidget()
        advanced_layout = QtWidgets.QVBoxLayout(self.advanced)
        advanced_layout.setContentsMargins(0, 0, 0, 0)
        self.advanced_toggle.toggled.connect(self.advanced.setVisible)
        scroll = QtWidgets.QScrollArea(widgetResizable=True)
        body = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(body)
        self.method = QtWidgets.QComboBox()
        for method in recovery.METHODS:
            self.method.addItem(method.label, method.id)
        self.controls.append(self.method)
        form.addRow("Metode:", self.method)
        self.description = QtWidgets.QLabel()
        self.description.setWordWrap(True)
        form.addRow(self.description)

        self.size = QtWidgets.QComboBox()
        self.size.addItems(["1k", "mini", "2k", "4k"])
        self.key = QtWidgets.QLineEdit()
        self.key.setPlaceholderText("Key valid 12 digit hex; kosong bila belum diketahui")
        self.kind = QtWidgets.QComboBox()
        self.kind.addItems(["A", "B"])
        self.block = QtWidgets.QSpinBox(maximum=255)
        self.target = QtWidgets.QSpinBox(maximum=255, value=4)
        self.target_kind = QtWidgets.QComboBox()
        self.target_kind.addItems(["A", "B"])
        self.single_target = QtWidgets.QCheckBox("Nested: hanya blok/key target")
        self.uid = QtWidgets.QLineEdit()
        self.uid.setPlaceholderText("UID reader attack / keygen: 4, 7, atau 10 byte")
        for label, control in (("Ukuran kartu:", self.size), ("Key diketahui:", self.key),
                               ("Tipe key asal:", self.kind), ("Blok key asal:", self.block),
                               ("Blok target:", self.target), ("Tipe key target:", self.target_kind),
                               ("", self.single_target), ("UID (opsional):", self.uid)):
            form.addRow(label, control)
            self.controls.append(control)

        self.dictionary = self.file_field(form, "Dictionary (.dic):", "Dictionary (*.dic *.txt);;Semua file (*.*)")
        self.datafile = self.file_field(form, "File nonce / emulator:", "Semua file (*.*)")
        self.executable = self.file_field(form, "Executable tool offline:", "Executable (*.exe);;Semua file (*.*)")
        self.executable.setPlaceholderText("Kosong = cari tool di PATH dan instalasi Proxmark3")
        self.offline = QtWidgets.QCheckBox("Jalankan PM3 offline (file nonce/trace; tanpa COM)")
        self.offline.setToolTip("Untuk hardnested -r, decrypt, keygen berbasis UID, atau trace dari file. Metode kartu memerlukan koneksi.")
        form.addRow(self.offline)
        self.controls.append(self.offline)
        self.extra = QtWidgets.QLineEdit()
        self.extra.setPlaceholderText("Semua opsi lain dari Help, misalnya --slow; untuk script: nama script dan opsi")
        form.addRow("Parameter tambahan:", self.extra)
        self.controls.append(self.extra)
        self.minutes = QtWidgets.QSpinBox(minimum=1, maximum=10080, value=120)
        self.minutes.setSuffix(" menit")
        form.addRow("Batas waktu per proses:", self.minutes)
        self.controls.append(self.minutes)
        self.output = QtWidgets.QLineEdit(os.path.abspath("recovery_sessions"))
        form.addRow("Folder log/hasil:", self.output)
        self.controls.append(self.output)
        self.command = QtWidgets.QLineEdit()
        self.command.setToolTip("Bisa diedit untuk semua opsi pada metode terpilih. Klik Susun perintah untuk memperbarui dari kolom di atas.")
        self.command.textEdited.connect(lambda: setattr(self, "_manual_command", True))
        form.addRow("Perintah (bisa diedit):", self.command)
        self.controls.append(self.command)
        scroll.setWidget(body)
        advanced_layout.addWidget(scroll, 1)

        actions = QtWidgets.QHBoxLayout()
        for title, callback in (("Susun perintah", self.compose), ("Help metode", self.help),
                                ("Metode dari PM3", self.discover), ("Daftar script", self.scripts),
                                ("Jalankan metode pilihan", self.run)):
            button = QtWidgets.QPushButton(title)
            button.clicked.connect(callback)
            actions.addWidget(button)
            self.controls.append(button)
        advanced_layout.addLayout(actions)
        outer.addWidget(self.advanced, 1)
        self.advanced.hide()
        self.results = QtWidgets.QTableWidget(0, 3)
        self.results.setHorizontalHeaderLabels(["Sektor", "Tipe", "Key ditemukan"])
        self.results.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.results.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        outer.addWidget(self.results, 1)
        self.method.currentIndexChanged.connect(self.changed)
        for control in (self.key, self.uid, self.dictionary, self.datafile, self.extra):
            control.textChanged.connect(lambda: setattr(self, "_manual_command", False))
        for control in (self.size, self.kind, self.target_kind):
            control.currentIndexChanged.connect(lambda: setattr(self, "_manual_command", False))
        for control in (self.block, self.target):
            control.valueChanged.connect(lambda: setattr(self, "_manual_command", False))
        for control in (self.offline, self.single_target):
            control.toggled.connect(lambda: setattr(self, "_manual_command", False))
        self.changed()

    def file_field(self, form, label, filters):
        field = QtWidgets.QLineEdit()
        row = QtWidgets.QHBoxLayout()
        row.addWidget(field, 1)
        pick = QtWidgets.QPushButton("Pilih…")
        pick.clicked.connect(lambda: self.window._pick_into(field, filters))
        row.addWidget(pick)
        form.addRow(label, row)
        self.controls += [field, pick]
        return field

    def selected(self):
        return self.methods[self.method.currentData()]

    def options(self):
        return dict(size=self.size.currentText(), key=self.key.text().strip(), key_type=self.kind.currentText(),
                    block=self.block.value(), target=self.target.value(), target_type=self.target_kind.currentText(),
                    single_target=self.single_target.isChecked(), uid=self.uid.text().strip(),
                    dictionary=self.dictionary.text().strip(), datafile=self.datafile.text().strip(),
                    offline=self.offline.isChecked(), extra=self.extra.text().strip())

    def changed(self):
        self._manual_command = False
        method = self.selected()
        self.description.setText(method.description)
        self.extra.clear()
        self.offline.setChecked(method.external or method.id == "decrypt")
        if self.advanced_toggle.isChecked():
            self.summary.setText(method.label + ": " + method.description)
        self.results.setRowCount(0)
        # Tampilkan template untuk metode yang belum memiliki key; validasi dilakukan saat susun/run.
        self.command.setText(method.command + (" " + method.defaults if method.defaults else ""))
        if method.id not in {"nested", "staticnested"}:
            self.compose()

    def compose(self):
        try:
            self.command.setText(recovery.build_command(self.selected(), **self.options()))
            self._manual_command = False
            return True
        except (ValueError, recovery.RecoveryError) as exc:
            self.window._append(f"Parameter: {exc}\n", "err")
            return False

    def set_busy(self, busy):
        for control in self.controls:
            control.setEnabled(not busy)
        self.stop.setEnabled(busy and self.cancel_event is not None)
        if not busy:
            self.timer.stop()
            self._started_at = None
            self.cancel_event = None

    def update_elapsed(self):
        if self._started_at is not None and self._is_recovery and self.cancel_event and not self.cancel_event.is_set():
            elapsed = int(time.monotonic() - self._started_at)
            self.summary.setText(f"Recovery sedang berjalan — {elapsed // 60:02}:{elapsed % 60:02}. "
                                 "Biarkan kartu tetap pada antena. Hasil muncul otomatis setelah proses selesai.")

    def cancel(self):
        if self.cancel_event:
            self.cancel_event.set()
            self.summary.setText("Menghentikan proses recovery. Output yang terkumpul tetap disimpan.")
            self.stop.setEnabled(False)

    def start(self, title, fn, on_result=None):
        if self.window._worker and self.window._worker.isRunning():
            self.window._append("Masih ada operasi berjalan.\n", "err")
            return
        self.cancel_event = threading.Event()
        self._operation_title = title
        self.last_report = None
        self._started_at = time.monotonic()
        self.timer.start()
        event = self.cancel_event
        self.window._start(title, lambda emit: fn(self.window._client(), emit, event), on_result=on_result)

    def help(self):
        self._is_recovery = False
        method = self.selected()
        executable = self.executable.text().strip()
        offline = self.offline.isChecked()
        self.start("Help recovery", lambda client, emit, event: recovery.method_help(
            client, method, executable=executable, offline=offline, emit=emit, cancel=event))

    def scripts(self):
        self._is_recovery = False
        self.start("Daftar script PM3", lambda client, emit, event: client.run_live(
            "script list", timeout=45, emit=emit, cancel=event))

    def discover(self):
        self._is_recovery = False
        self.start("Daftar metode recovery", lambda client, emit, event: recovery.discover(
            client, emit=emit, cancel=event), on_result=self.add_methods)

    def add_methods(self, methods):
        for method in methods:
            if method.id not in self.methods:
                self.methods[method.id] = method
                self.method.addItem(method.label, method.id)
        self.summary.setText(f"Daftar recovery dari client dimuat. {len(methods)} metode tambahan ditemukan; lihat log untuk daftar lengkap.")

    def run(self):
        method = self.selected()
        if not self._manual_command and not self.compose():
            return
        try:
            command = recovery.single_command(self.command.text())
        except recovery.RecoveryError as exc:
            self.window._append(str(exc) + "\n", "err")
            return
        # Snapshot semua masukan di thread GUI, sebelum worker mulai.
        settings = dict(timeout=self.minutes.value() * 60, output_dir=self.output.text().strip() or "recovery_sessions",
                        executable=self.executable.text().strip(), offline=self.offline.isChecked(),
                        size=self.size.currentText())
        self.results.setRowCount(0)
        self._is_recovery = True
        self.summary.setText("Recovery berjalan. Output langsung dan log tersedia di bawah.")
        self.start("Recovery Keys", lambda client, emit, event: recovery.run_recovery(
            client, method, command, emit=emit, cancel=event, **settings), on_result=self.show_report)

    def run_auto(self):
        if self.window._worker and self.window._worker.isRunning():
            return
        # Parameter eksperimen/metode offline tidak masuk ke jalur satu klik.
        self.advanced_toggle.setChecked(False)
        self.results.setRowCount(0)
        self._is_recovery = True
        self.summary.setText("Recovery otomatis dimulai. Biarkan kartu tetap pada antena dan tunggu hasilnya.")
        self.start("Recovery otomatis", lambda client, emit, event: recovery.run_auto(
            client, output_dir=self._auto_output, emit=emit, cancel=event), on_result=self.show_report)

    def operation_finished(self, ok, title):
        if title != self._operation_title or not self._is_recovery:
            return
        if self.last_report is None:
            self.summary.setText("Recovery gagal dimulai. Penyebabnya ditampilkan pada log di bawah.")
            self.window.statusBar().showMessage("Gagal: " + title)
        else:
            self.window.statusBar().showMessage(self.summary.text())

    def show_report(self, report):
        self.timer.stop()
        self.last_report = report
        rows = list(report["keys"])
        assigned = {row["key"] for row in rows}
        rows += [{"sector": "?", "type": "?", "key": key} for key in report["unique_keys"] if key not in assigned]
        self.results.setRowCount(len(rows))
        for row, item in enumerate(rows):
            for col, name in enumerate(("sector", "type", "key")):
                self.results.setItem(row, col, QtWidgets.QTableWidgetItem(str(item[name])))
        labels = {"keys_found": "Key ditemukan", "no_keys": "Selesai, belum ditemukan key", "completed": "Selesai",
                  "failed": "Recovery gagal", "timeout": "Batas waktu tercapai", "cancelled": "Dihentikan"}
        text = (f"{labels.get(report['status'], report['status'])} | Key sektor: {len(report['keys'])} | "
                f"Key unik: {len(report['unique_keys'])} | Key sektor normal belum terpulihkan: {len(report['missing'])}")
        if report["expected_extra_sectors"]:
            text += f" | Key sektor ekstra belum terpulihkan: {len(report['missing_extra'])}"
        text += f". Hasil: {report['session_dir']}"
        if report.get("error"):
            text += ". " + report["error"]
        self.summary.setText(text)
        self.window._append(text + "\n", "ok" if report["status"] in {"completed", "keys_found"} else "err")
