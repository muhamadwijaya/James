"""Kolektor page: batch name (Alb-NNNNNN), Start/Done, CSV export, manual link input, table."""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
)

import collector as collector_mod
import icons
import theme
from widgets import Card, IconBox

MAX_DISPLAY = 300
COLUMNS = ["No", "Waktu diterima", "Code", "Link / String asli", "Nama baru", "Status"]
STATUS_COLOR = dict(theme.STATUS_COLORS, manual=theme.CYAN)
STATUS_LABEL_TO_KEY = {v: k for k, v in collector_mod.STATUS_LABEL.items()}


def _status_key(row: dict) -> str:
    status = row.get("status", "")
    return STATUS_LABEL_TO_KEY.get(status, status)


def _status_label(row: dict) -> str:
    status = row.get("status", "")
    return collector_mod.STATUS_LABEL.get(status, status or "-")


class CollectModel(QAbstractTableModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[dict] = []

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self._rows = list(reversed(rows[-MAX_DISPLAY:]))   # newest first
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return [row["no"], row["received"][-8:] if row["received"] else "", row["code"] or "-",
                    row["link"], row["name"] or "-", _status_label(row)][col]
        if role == Qt.ItemDataRole.ToolTipRole and col == 3:
            return row["link"]
        if role == Qt.ItemDataRole.ToolTipRole and col == 4:
            return row["name"]
        if role == Qt.ItemDataRole.ForegroundRole and col == 5:
            return QColor(STATUS_COLOR.get(_status_key(row), theme.MUTED))
        return None


class CollectorPage(Card):
    """Emits start/done so the main window can save settings and know the session state."""

    sessionChanged = Signal()

    def __init__(self, collector: collector_mod.Collector, parent=None) -> None:
        super().__init__(parent=parent, margins=(16, 12, 16, 14))
        self.collector = collector
        self._dirty = False

        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(IconBox("grid", theme.BLUE, 40))
        texts = QVBoxLayout()
        texts.setSpacing(1)
        title = QLabel("Kolektor Data")
        title.setObjectName("cardTitle")
        sub = QLabel("Kumpulkan data dari FTP ke satu file CSV per batch (duplikat diabaikan)")
        sub.setObjectName("cardSubtitle")
        texts.addWidget(title)
        texts.addWidget(sub)
        header.addLayout(texts)
        header.addStretch(1)
        self.session_label = QLabel()
        self.session_label.setStyleSheet("font-weight: 600;")
        header.addWidget(self.session_label)
        self.body.addLayout(header)

        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(9)
        form.setColumnStretch(1, 1)

        name_row = QHBoxLayout()
        name_row.setSpacing(0)
        prefix = QLabel(collector_mod.BATCH_PREFIX)
        prefix.setObjectName("mono")
        prefix.setStyleSheet("font-size: 11pt; font-weight: 700; padding: 0 2px;")
        self.number_edit = QLineEdit("000000")
        self.number_edit.setMaxLength(10)
        self.number_edit.setFixedWidth(130)
        self.number_edit.setInputMask("")
        self.number_edit.setPlaceholderText("000000")
        self.number_edit.setStyleSheet("font-family: monospace; font-size: 11pt; font-weight: 700;")
        self.number_edit.textEdited.connect(self._on_number_edited)
        name_row.addWidget(prefix)
        name_row.addWidget(self.number_edit)
        name_row.addStretch(1)

        self.folder_edit = QLineEdit()
        browse = QPushButton("Browse...")
        browse.setIcon(icons.icon("folder", theme.TEXT, 16))
        browse.setFixedWidth(120)
        browse.clicked.connect(self._browse)

        label_name = QLabel("Nama file")
        label_name.setObjectName("formLabel")
        label_folder = QLabel("Folder CSV")
        label_folder.setObjectName("formLabel")
        form.addWidget(label_name, 0, 0)
        form.addLayout(name_row, 0, 1, 1, 3)
        form.addWidget(label_folder, 1, 0)
        form.addWidget(self.folder_edit, 1, 1, 1, 2)
        form.addWidget(browse, 1, 3, Qt.AlignmentFlag.AlignRight)
        self.body.addLayout(form)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        self.start_btn = QPushButton("  Start")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.setIcon(icons.icon("play", "#ffffff", 16))
        self.start_btn.setMinimumHeight(42)
        self.start_btn.clicked.connect(self._start)
        self.done_btn = QPushButton("  Done")
        self.done_btn.setIcon(icons.icon("check", "#ffffff", 16))
        self.done_btn.setMinimumHeight(42)
        self.done_btn.setStyleSheet("QPushButton { background: #11223f; border: 1px solid #2d4a78; border-radius: 9px;"
                                    " font-size: 11pt; font-weight: 600; }"
                                    "QPushButton:hover { background: #16294b; } QPushButton:disabled { color: #7589a8; }")
        self.done_btn.clicked.connect(self._done)
        self.export_btn = QPushButton("  Export CSV")
        self.export_btn.setIcon(icons.icon("file_text", theme.TEXT, 16))
        self.export_btn.setMinimumHeight(42)
        self.export_btn.clicked.connect(self._export)
        self.open_btn = QPushButton("  Buka folder")
        self.open_btn.setIcon(icons.icon("folder", theme.TEXT, 16))
        self.open_btn.setMinimumHeight(42)
        self.open_btn.clicked.connect(self._open_folder)
        for b in (self.start_btn, self.done_btn, self.export_btn, self.open_btn):
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            buttons.addWidget(b)
        self.body.addLayout(buttons)

        manual = QHBoxLayout()
        manual.setSpacing(10)
        manual_label = QLabel("Tambah manual")
        manual_label.setObjectName("formLabel")
        self.manual_edit = QLineEdit()
        self.manual_edit.setPlaceholderText("Tempel link / string, mis. https&&&aslibos.com&scan&BXXAXESPP2026_10_16_08_00_00.jpg")
        self.manual_edit.returnPressed.connect(self._add_manual)
        self.add_btn = QPushButton("Tambah")
        self.add_btn.setIcon(icons.icon("download", theme.TEXT, 16))
        self.add_btn.clicked.connect(self._add_manual)
        manual.addWidget(manual_label)
        manual.addWidget(self.manual_edit, 1)
        manual.addWidget(self.add_btn)
        self.body.addLayout(manual)

        counters = QHBoxLayout()
        counters.setSpacing(12)
        self.count_label = QLabel()
        self.count_label.setStyleSheet(f"color: {theme.GREEN}; font-weight: 600;")
        self.dup_label = QLabel()
        self.dup_label.setStyleSheet(f"color: {theme.ORANGE}; font-weight: 600;")
        self.file_label = QLabel()
        self.file_label.setObjectName("muted")
        counters.addWidget(self.count_label)
        counters.addWidget(self.dup_label)
        counters.addStretch(1)
        counters.addWidget(self.file_label)
        self.body.addLayout(counters)

        self.model = CollectModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(28)
        hh = self.table.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        widths = {0: 56, 1: 92, 2: 130, 4: 230, 5: 120}
        for col in range(len(COLUMNS)):
            if col == 3:
                hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
            else:
                hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(col, widths[col])
        self.body.addWidget(self.table, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self._update_state()

    # ------------------------------------------------------------ public API
    def set_config(self, number: str, folder: str) -> None:
        self.number_edit.setText("".join(c for c in (number or "000000") if c.isdigit()) or "000000")
        self.folder_edit.setText(folder)
        self.folder_edit.setCursorPosition(0)

    def current_number(self) -> str:
        return self.number_edit.text() or "000000"

    def current_folder(self) -> str:
        return self.folder_edit.text().strip()

    def feed_event(self, event: dict) -> None:
        """Called by the main window for every received-file event."""
        if self.collector.active:
            if self.collector.add_event(event).outcome in ("added", "duplicate"):
                self._dirty = True

    # ------------------------------------------------------------ actions
    def _on_number_edited(self, text: str) -> None:
        digits = "".join(c for c in text if c.isdigit())
        if digits != text:
            pos = self.number_edit.cursorPosition()
            self.number_edit.setText(digits)
            self.number_edit.setCursorPosition(max(0, pos - 1))

    def _browse(self) -> None:
        start = self.current_folder() or str(collector_mod.Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Pilih folder CSV kolektor", start)
        if folder:
            self.folder_edit.setText(str(collector_mod.Path(folder)))
            self.folder_edit.setCursorPosition(0)

    def _start(self) -> None:
        number = self.current_number()
        if not collector_mod.BATCH_RE.match(collector_mod.batch_name(number)):
            QMessageBox.warning(self, "Nama file", "Nomor batch harus berupa angka, mis. 000123.")
            return
        folder = self.current_folder()
        if not folder:
            QMessageBox.warning(self, "Folder CSV", "Pilih folder penyimpanan CSV terlebih dahulu.")
            return
        try:
            path = self.collector.start(number, folder)
        except OSError as exc:
            QMessageBox.warning(self, "Start", f"CSV tidak bisa dibuka:\n{exc}")
            return
        self._dirty = True
        self._refresh()
        self._update_state()
        self.sessionChanged.emit()
        if len(self.collector.rows) > 0:
            self.file_label.setToolTip(str(path))

    def _done(self) -> None:
        self.collector.done()
        self._update_state()
        self.sessionChanged.emit()

    def _export(self) -> None:
        if not self.collector.rows:
            QMessageBox.information(self, "Export CSV", "Belum ada data untuk diexport.")
            return
        default = self.collector.batch or collector_mod.batch_name(self.current_number())
        start = str(collector_mod.Path(self.current_folder() or ".") / f"{default}_export.csv")
        dest, _ = QFileDialog.getSaveFileName(self, "Export CSV", start, "CSV (*.csv)")
        if not dest:
            return
        try:
            path = self.collector.export(dest)
        except OSError as exc:
            QMessageBox.warning(self, "Export CSV", f"Gagal menyimpan:\n{exc}")
            return
        QMessageBox.information(self, "Export CSV", f"Tersimpan: {path}")

    def _open_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        folder = collector_mod.Path(self.current_folder())
        if folder.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        else:
            QMessageBox.information(self, "Folder CSV", "Folder belum ada. Folder dibuat saat klik Start.")

    def _add_manual(self) -> None:
        if not self.collector.active:
            QMessageBox.information(self, "Tambah manual", "Klik Start dulu untuk mulai mengumpulkan ke CSV.")
            return
        text = self.manual_edit.text().strip()
        if not text:
            return
        result = self.collector.add_link(text)
        if result.outcome == "duplicate":
            self.manual_edit.selectAll()
        else:
            self.manual_edit.clear()
        self._dirty = True
        self._refresh()

    # ------------------------------------------------------------ view
    def _refresh(self) -> None:
        if self._dirty:
            self.model.set_rows(self.collector.rows)
            self._dirty = False
        self.count_label.setText(f"Terkumpul: {len(self.collector.rows)}")
        self.dup_label.setText(f"Duplikat diabaikan: {self.collector.duplicates}")
        if self.collector.csv_path:
            self.file_label.setText(f"File: {self.collector.csv_path.name}")
            self.file_label.setToolTip(str(self.collector.csv_path))
        else:
            self.file_label.setText("")

    def _update_state(self) -> None:
        active = self.collector.active
        self.start_btn.setEnabled(not active)
        self.done_btn.setEnabled(active)
        self.number_edit.setEnabled(not active)
        self.folder_edit.setEnabled(not active)
        self.add_btn.setEnabled(active)
        self.manual_edit.setEnabled(active)
        if active:
            self.session_label.setText(f"●  {self.collector.batch} - aktif")
            self.session_label.setStyleSheet(f"color: {theme.GREEN}; font-weight: 600;")
        elif self.collector.batch:
            self.session_label.setText(f"●  {self.collector.batch} - selesai")
            self.session_label.setStyleSheet(f"color: {theme.MUTED}; font-weight: 600;")
        else:
            self.session_label.setText("●  Belum ada sesi")
            self.session_label.setStyleSheet(f"color: {theme.MUTED}; font-weight: 600;")
        self._refresh()
