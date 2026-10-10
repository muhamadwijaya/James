"""Entry kode BK/tanggal dan preview penulisan chip ink baru."""

from datetime import date
from pathlib import Path
import threading

from PySide6 import QtCore, QtGui, QtWidgets

from . import dumpview, ink


class InkPanel(QtWidgets.QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.base_source = None
        self.source = None
        self.fields_supported = False
        self.plan = None
        self.cancel_event = None
        self.operation_title = None
        self.busy = False
        layout = QtWidgets.QVBoxLayout(self)
        info = QtWidgets.QLabel("Isi chip baru kosong dengan data dan key dari chip belum terpakai. "
                               "Kode BK dan tanggal dapat diisi; hasil HEX/ASCII diperbarui otomatis.")
        info.setWordWrap(True)
        layout.addWidget(info)

        form = QtWidgets.QGridLayout()
        self.preset = QtWidgets.QComboBox()
        for value, label in ink.PRESETS:
            self.preset.addItem(label, value)
        self.preset.addItem("Dump acuan sendiri…", "file")
        self.file = QtWidgets.QLineEdit()
        self.file.setReadOnly(True)
        self.file.setPlaceholderText("Pilih dump lengkap .bin / .eml / .json")
        self.browse = QtWidgets.QPushButton("Pilih dump…")
        self.browse.clicked.connect(self.pick_source)
        form.addWidget(QtWidgets.QLabel("Acuan:"), 0, 0)
        form.addWidget(self.preset, 0, 1)
        form.addWidget(self.file, 0, 2)
        form.addWidget(self.browse, 0, 3)
        self.mode = QtWidgets.QComboBox()
        for value, label in ink.MODES.items():
            self.mode.addItem(label, value)
        self.folder = QtWidgets.QLineEdit(str(Path.cwd() / "ink_writes"))
        self.pick_folder_button = QtWidgets.QPushButton("Folder hasil…")
        self.pick_folder_button.clicked.connect(self.pick_folder)
        form.addWidget(QtWidgets.QLabel("Mode:"), 1, 0)
        form.addWidget(self.mode, 1, 1)
        form.addWidget(self.folder, 1, 2)
        form.addWidget(self.pick_folder_button, 1, 3)
        layout.addLayout(form)

        entries = QtWidgets.QGridLayout()
        self.product = QtWidgets.QLineEdit()
        self.product.setMaxLength(7)
        self.product.setPlaceholderText("BKA236T")
        self.product.setToolTip("Kode produk 1–7 huruf kapital A–Z atau angka 0–9. "
                                "Mengubah kode tidak mengubah karakteristik atau kapasitas produk pada acuan.")
        self.date_entry = QtWidgets.QDateEdit()
        self.date_entry.setCalendarPopup(True)
        self.date_entry.setDisplayFormat("dd/MM/yyyy")
        self.date_entry.setDateRange(QtCore.QDate(2000, 1, 1), QtCore.QDate(2099, 12, 31))
        self.date_entry.setToolTip("Tanggal pada record chip. Jenis tanggal mengikuti acuan; "
                                   "belum ditetapkan sebagai tanggal produksi atau kedaluwarsa.")
        self.date_ascii = QtWidgets.QLineEdit()
        self.source_uid = QtWidgets.QLineEdit()
        self.ascii_entry = QtWidgets.QLineEdit()
        self.key_entry = QtWidgets.QLineEdit()
        for edit in (self.source_uid, self.ascii_entry, self.key_entry, self.date_ascii):
            edit.setReadOnly(True)
        entries.addWidget(QtWidgets.QLabel("Kode BK / produk:"), 0, 0)
        entries.addWidget(self.product, 0, 1)
        entries.addWidget(QtWidgets.QLabel("UID acuan:"), 0, 2)
        entries.addWidget(self.source_uid, 0, 3)
        entries.addWidget(QtWidgets.QLabel("Tanggal chip:"), 1, 0)
        entries.addWidget(self.date_entry, 1, 1)
        entries.addWidget(QtWidgets.QLabel("Tanggal YYMMDD:"), 1, 2)
        entries.addWidget(self.date_ascii, 1, 3)
        entries.addWidget(QtWidgets.QLabel("ASCII blok 5:"), 2, 0)
        entries.addWidget(self.ascii_entry, 2, 1)
        entries.addWidget(QtWidgets.QLabel("Key acuan:"), 2, 2)
        entries.addWidget(self.key_entry, 2, 3)
        self.key_entry.setToolTip("Key A/B setiap sektor tersedia pada tab Key. Target awal harus menggunakan FFFFFFFFFFFF.")
        layout.addLayout(entries)
        self.field_note = QtWidgets.QLabel()
        self.field_note.setWordWrap(True)
        layout.addWidget(self.field_note)

        actions = QtWidgets.QHBoxLayout()
        self.preview_button = QtWidgets.QPushButton("1. Baca chip kosong + Preview")
        self.write_button = QtWidgets.QPushButton("2. Write Chip Baru")
        self.stop_button = QtWidgets.QPushButton("Hentikan")
        self.export_button = QtWidgets.QPushButton("Simpan data + key…")
        self.preview_button.clicked.connect(self.preview)
        self.write_button.clicked.connect(self.write)
        self.stop_button.clicked.connect(self.cancel)
        self.export_button.clicked.connect(self.export)
        for button in (self.preview_button, self.write_button, self.stop_button, self.export_button):
            actions.addWidget(button)
        layout.addLayout(actions)
        self.summary = QtWidgets.QLabel()
        self.summary.setWordWrap(True)
        self.summary.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        layout.addWidget(self.summary)

        self.details = QtWidgets.QTabWidget()
        self.data_table = self.table(("Blok", "Data untuk ditulis (HEX)", "ASCII"))
        self.keys_table = self.table(("Sektor", "Key A", "AC / GPB", "Key B"))
        self.preview_table = self.table(("Blok", "Sebelum (HEX)", "Sesudah (HEX)", "ASCII hasil"))
        self.details.addTab(self.data_table, "Data / Entry")
        self.details.addTab(self.keys_table, "Key 16 sektor")
        self.details.addTab(self.preview_table, "Perubahan ke target")
        layout.addWidget(self.details, 1)
        self.preset.currentIndexChanged.connect(self.load_source)
        self.mode.currentIndexChanged.connect(self.invalidate)
        self.folder.textChanged.connect(self.invalidate)
        self.product.textChanged.connect(self.apply_fields)
        self.date_entry.dateChanged.connect(self.apply_fields)
        self.load_source()

    @staticmethod
    def table(columns):
        table = QtWidgets.QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setAlternatingRowColors(True)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        table.horizontalHeader().setStretchLastSection(True)
        table.setFont(QtGui.QFont("Consolas", 9))
        table.setMinimumHeight(130)
        return table

    @staticmethod
    def cells(table, row, values):
        for col, value in enumerate(values):
            item = QtWidgets.QTableWidgetItem(str(value))
            item.setToolTip(str(value))
            table.setItem(row, col, item)

    def invalidate(self, *_):
        self.plan = None
        self.preview_table.setRowCount(0)
        text = ("Chip biasa: blok 1–63 dan key mengikuti data pada form; UID chip baru dipertahankan."
                if self.mode.currentData() == "normal" else
                "Magic Gen1a: seluruh 64 blok mengikuti data pada form, termasuk UID acuan. Membutuhkan chip Gen1a kosong.")
        self.summary.setText(text + " Jalankan Preview sebelum Write.")
        self.set_busy(self.busy)

    def load_source(self, *_):
        self.invalidate()
        selection = self.preset.currentData()
        self.base_source = None
        self.source = None
        self.fields_supported = False
        self.field_note.clear()
        self.data_table.setRowCount(0)
        self.keys_table.setRowCount(0)
        for edit in (self.product, self.source_uid, self.ascii_entry, self.key_entry, self.date_ascii):
            edit.clear()
        if selection == "file":
            selection = self.file.text().strip()
            if not selection:
                self.summary.setText("Pilih dump lengkap dari chip belum terpakai.")
                self.set_busy(self.busy)
                return
        else:
            self.file.clear()
        try:
            self.base_source = self.source = ink.reference(selection)
        except Exception as exc:
            self.summary.setText(f"Acuan belum dimuat: {exc}")
            self.set_busy(self.busy)
            return
        product_blocked = self.product.blockSignals(True)
        date_blocked = self.date_entry.blockSignals(True)
        try:
            self.product.setText(self.source.product)
            try:
                fields = ink.read_fields(self.base_source)
            except ink.InkError as exc:
                self.date_entry.setSpecialValueText("Format belum didukung")
                self.date_entry.setDate(self.date_entry.minimumDate())
                self.field_note.setText(f"{exc} Acuan tetap dapat disalin tanpa personalisasi.")
            else:
                self.fields_supported = True
                self.date_entry.setSpecialValueText("")
                self.date_entry.setDate(QtCore.QDate(fields.record_date.year, fields.record_date.month,
                                                    fields.record_date.day))
                self.date_ascii.setText(fields.record_date.strftime("%y%m%d"))
                self.field_note.setText("Isi kode BK dan tanggal DD/MM/YYYY. Tanggal teks dan biner disinkronkan. "
                                        "Jenis tanggal mengikuti acuan.")
        finally:
            self.product.blockSignals(product_blocked)
            self.date_entry.blockSignals(date_blocked)
        self.render_source()
        self.set_busy(self.busy)

    def render_source(self):
        if not self.source:
            return
        self.source_uid.setText(self.source.uid)
        self.ascii_entry.setText(dumpview.block_ascii(self.source.data[80:96]))
        keyset = sorted({self.source.data[(s * 4 + 3) * 16:(s * 4 + 3) * 16 + 6].hex().upper()
                         for s in range(16)})
        self.key_entry.setText(" / ".join(keyset) if len(keyset) <= 2 else "Lihat key per sektor")
        self.data_table.setRowCount(64)
        self.keys_table.setRowCount(16)
        for block in range(64):
            raw = self.source.data[block * 16:(block + 1) * 16]
            self.cells(self.data_table, block, (
                f"{block} (trailer)" if block % 4 == 3 else block, raw.hex(" ").upper(), dumpview.block_ascii(raw)))
            if block % 4 == 3:
                self.cells(self.keys_table, block // 4, (
                    block // 4, raw[:6].hex().upper(), raw[6:10].hex().upper(), raw[10:].hex().upper()))

    def apply_fields(self, *_):
        if not self.base_source or not self.fields_supported:
            return
        chosen = self.date_entry.date()
        self.date_ascii.setText(chosen.toString("yyMMdd"))
        try:
            self.source = ink.customize_reference(self.base_source, self.product.text(),
                                                  date(chosen.year(), chosen.month(), chosen.day()))
        except ink.InkError as exc:
            self.source = None
            self.invalidate()
            self.data_table.setRowCount(0)
            self.keys_table.setRowCount(0)
            self.ascii_entry.clear()
            self.field_note.setText(str(exc))
            self.summary.setText("Perbaiki kode BK/tanggal sebelum Preview atau Write.")
            return
        self.render_source()
        self.invalidate()
        if self.source.customization:
            self.field_note.setText("Kode/tanggal kustom diterapkan pada data. Field validasi lain mengikuti acuan; "
                                    "penerimaan printer belum diuji.")
        else:
            self.field_note.setText("Isi kode BK dan tanggal DD/MM/YYYY. Tanggal teks dan biner disinkronkan. "
                                    "Jenis tanggal mengikuti acuan.")

    def pick_source(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Dump acuan chip belum terpakai", "", "Dump (*.bin *.eml *.json);;Semua file (*)")
        if filename:
            self.file.setText(filename)
            self.preset.setCurrentIndex(self.preset.findData("file"))
            self.load_source()

    def pick_folder(self):
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Folder backup dan hasil ink")
        if directory:
            self.folder.setText(directory)

    def preview(self):
        if not self.source or not self.folder.text().strip():
            self.summary.setText("Pilih acuan lengkap dan folder hasil terlebih dahulu.")
            return
        self.plan = None
        self.cancel_event = threading.Event()
        self.operation_title = "Preview Chip Ink Baru"
        source, mode, folder = self.source, self.mode.currentData(), self.folder.text().strip()
        cancel = self.cancel_event
        self.summary.setText("Membaca chip dan menyiapkan backup. Belum ada data yang ditulis.")
        self.window._start(self.operation_title, lambda emit: ink.prepare(
            self.window._client(), source, mode, folder, emit, cancel), on_result=self.show_plan)

    @QtCore.Slot(object)
    def show_plan(self, plan):
        self.plan = plan
        self.preview_table.setRowCount(len(plan.changes))
        for row, change in enumerate(plan.changes):
            self.cells(self.preview_table, row, (change.block, change.before.hex(" ").upper(),
                       change.after.hex(" ").upper(), dumpview.block_ascii(change.after)))
        self.details.setCurrentWidget(self.preview_table)
        self.summary.setText(f"Chip kosong terkonfirmasi. {len(plan.changes)} blok akan ditulis. "
                             f"UID {plan.uid} → {plan.after[:4].hex().upper()}. "
                             "Data dan key mengikuti form. Klik Write Chip Baru.")
        if plan.reference.customization:
            chosen = plan.reference.customization
            self.summary.setText(self.summary.text() +
                                 f" Kode {chosen.product}, tanggal {chosen.record_date:%d/%m/%Y}. "
                                 "Penerimaan printer belum diuji.")
        self.set_busy(self.busy)

    def write(self):
        if not self.plan:
            self.summary.setText("Jalankan Preview pada chip kosong sebelum Write.")
            return
        plan, self.plan = self.plan, None
        self.cancel_event = threading.Event()
        cancel = self.cancel_event
        self.operation_title = "Write Chip Ink Baru"
        self.summary.setText("Menulis data, lalu key setiap sektor, dan memverifikasi hasil…")
        self.window._start(self.operation_title, lambda emit: ink.execute(
            self.window._client(), plan, emit, cancel), on_result=self.show_result)

    @QtCore.Slot(object)
    def show_result(self, report):
        detail = ("64 blok cocok dengan data pada form, termasuk UID acuan." if report.exact_with_uid else
                  "Blok 1–63 dan key cocok dengan data pada form; UID chip baru dipertahankan.")
        self.summary.setText(f"TERVERIFIKASI — UID {report.uid}. {detail} Hasil: {report.session_dir}. "
                             "Verifikasi ini memastikan data tersimpan; penerimaan printer belum diuji.")

    def cancel(self):
        if self.cancel_event:
            self.cancel_event.set()
            self.stop_button.setEnabled(False)
            self.summary.setText("Menghentikan setelah perintah PM3 aktif selesai. Periksa journal hasil.")

    def operation_finished(self, ok, title):
        if title != self.operation_title:
            return
        self.cancel_event = None
        self.operation_title = None
        if not ok:
            self.plan = None
            self.summary.setText("Proses belum berhasil. Detail ada di log; backup dan journal tersedia di folder hasil.")
        self.set_busy(False)

    def set_busy(self, busy):
        self.busy = busy
        for widget in (self.preset, self.browse, self.mode, self.folder, self.pick_folder_button):
            widget.setEnabled(not busy)
        self.product.setReadOnly(not self.fields_supported)
        self.product.setEnabled(not busy and self.base_source is not None)
        self.date_entry.setEnabled(not busy and self.fields_supported)
        self.preview_button.setEnabled(not busy and self.source is not None)
        self.write_button.setEnabled(not busy and self.plan is not None)
        self.export_button.setEnabled(not busy and self.source is not None)
        self.stop_button.setEnabled(busy and self.cancel_event is not None and not self.cancel_event.is_set())

    def export(self):
        if not self.source:
            return
        suggested = f"hf-mf-{self.source.uid}-unused.bin"
        if self.source.customization:
            chosen = self.source.customization
            suggested = f"hf-mf-{self.source.uid}-{chosen.product}-{chosen.record_date:%y%m%d}.bin"
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Simpan data chip dan key", suggested, "Dump (*.bin)")
        if filename:
            try:
                files = ink.export_reference(self.source, filename)
                self.window._append("Data chip dan key disimpan:\n" + "\n".join(files) + "\n", "ok")
            except Exception as exc:
                self.window._append(f"Gagal menyimpan acuan: {exc}\n", "err")
