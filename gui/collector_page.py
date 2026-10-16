"""Kolektor page: TCP/IP client (server IP + port) -> batch CSV Alb-NNNNNN with Start/Done.

Separate from the FTP photo rename: the Kolektor has its own connection.
"""
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
    QSpinBox,
    QTableView,
    QVBoxLayout,
)

import collector as collector_mod
import icons
import theme
from tcp_receiver import TcpReceiver
from widgets import Card, IconBox

MAX_DISPLAY = 300
COLUMNS = ["No", "Data", "Timestamp"]
CONN_COLOR = {"connected": theme.GREEN, "connecting": theme.ORANGE, "retrying": theme.RED, "stopped": theme.MUTED}


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
            return [row["no"], row["data"], row["timestamp"]][col]
        if role == Qt.ItemDataRole.ToolTipRole and col == 1:
            return row["data"]
        if role == Qt.ItemDataRole.ForegroundRole and col == 2:
            return QColor(theme.MUTED)
        return None


class CollectorPage(Card):
    """Emits start/done so the main window can save settings and know the session state."""

    sessionChanged = Signal()
    logMessage = Signal(str, str)      # level, text

    def __init__(self, collector: collector_mod.Collector, parent=None) -> None:
        super().__init__(parent=parent, margins=(16, 12, 16, 14))
        self.collector = collector
        self._dirty = False
        self._last_logged = ""
        self._error_shown = False
        self.receiver = TcpReceiver(self)
        self.receiver.dataReceived.connect(self._on_data)
        self.receiver.statusChanged.connect(self._on_conn_status)

        header = QHBoxLayout()
        header.setSpacing(12)
        header.addWidget(IconBox("grid", theme.BLUE, 40))
        texts = QVBoxLayout()
        texts.setSpacing(1)
        title = QLabel("Kolektor Data (TCP/IP)")
        title.setObjectName("cardTitle")
        sub = QLabel("Sambung ke IP + Port server, data yang diterima masuk ke CSV per batch "
                     "(kolom Data dan Timestamp, duplikat diabaikan)")
        sub.setObjectName("cardSubtitle")
        texts.addWidget(title)
        texts.addWidget(sub)
        header.addLayout(texts)
        header.addStretch(1)
        status_col = QVBoxLayout()
        status_col.setSpacing(2)
        self.session_label = QLabel()
        self.session_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.conn_label = QLabel()
        self.conn_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        status_col.addWidget(self.session_label)
        status_col.addWidget(self.conn_label)
        header.addLayout(status_col)
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

        self.host_edit = QLineEdit()
        self.host_edit.setPlaceholderText("mis. 192.168.1.50")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(9004)
        self.port_spin.setFixedWidth(120)

        self.folder_edit = QLineEdit()
        browse = QPushButton("Browse...")
        browse.setIcon(icons.icon("folder", theme.TEXT, 16))
        browse.setFixedWidth(120)
        browse.clicked.connect(self._browse)

        label_name = QLabel("Nama file")
        label_name.setObjectName("formLabel")
        label_folder = QLabel("Folder CSV")
        label_folder.setObjectName("formLabel")
        label_host = QLabel("IP Server")
        label_host.setObjectName("formLabel")
        label_port = QLabel("Port")
        label_port.setObjectName("formLabel")
        form.addWidget(label_name, 0, 0)
        form.addLayout(name_row, 0, 1, 1, 3)
        form.addWidget(label_host, 1, 0)
        form.addWidget(self.host_edit, 1, 1)
        form.addWidget(label_port, 1, 2, Qt.AlignmentFlag.AlignRight)
        form.addWidget(self.port_spin, 1, 3, Qt.AlignmentFlag.AlignRight)
        form.addWidget(label_folder, 2, 0)
        form.addWidget(self.folder_edit, 2, 1, 1, 2)
        form.addWidget(browse, 2, 3, Qt.AlignmentFlag.AlignRight)
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
        self.manual_edit.setPlaceholderText("Ketik / tempel data lalu Enter (masuk ke CSV yang sama, duplikat diabaikan)")
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
        widths = {0: 64, 2: 180}
        for col in range(len(COLUMNS)):
            if col == 1:
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
    def set_config(self, number: str, folder: str, host: str = "", port: int = 9004) -> None:
        self.number_edit.setText("".join(c for c in (number or "000000") if c.isdigit()) or "000000")
        self.folder_edit.setText(folder)
        self.folder_edit.setCursorPosition(0)
        self.host_edit.setText(host)
        self.port_spin.setValue(port)

    def current_number(self) -> str:
        return self.number_edit.text() or "000000"

    def current_folder(self) -> str:
        return self.folder_edit.text().strip()

    def current_host(self) -> str:
        return self.host_edit.text().strip()

    def current_port(self) -> int:
        return self.port_spin.value()

    def shutdown(self) -> None:
        """Window closing: disconnect and close the CSV (same as Done)."""
        if self.collector.active:
            self._done()

    # ------------------------------------------------------------ receiving
    def _on_data(self, text: str) -> None:
        if self.collector.add(text).outcome in ("added", "duplicate"):
            self._dirty = True

    def _on_conn_status(self, state: str, message: str) -> None:
        color = CONN_COLOR.get(state, theme.MUTED)
        self.conn_label.setText(f"●  {message}")
        self.conn_label.setToolTip(message)
        self.conn_label.setStyleSheet(f"color: {color}; font-weight: 600;")
        # log changes only (a server that stays offline must not flood the log every retry)
        if state in ("connected", "retrying") and message != self._last_logged:
            self._last_logged = message
            self.logMessage.emit("info" if state == "connected" else "warn", f"Kolektor: {message}")

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
        host = self.current_host()
        if not host or any(c.isspace() for c in host):
            QMessageBox.warning(self, "IP Server", "Isi IP server yang mengirim data, mis. 192.168.1.50.")
            return
        folder = self.current_folder()
        if not folder:
            QMessageBox.warning(self, "Folder CSV", "Pilih folder penyimpanan CSV terlebih dahulu.")
            return
        try:
            path = self.collector.start(number, folder)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Start", f"CSV tidak bisa dipakai:\n{exc}")
            return
        self._dirty = True
        self._last_logged = ""
        self.logMessage.emit("info", f"Kolektor start: {path.name} ({len(self.collector.rows)} data lama), "
                                     f"server {host}:{self.current_port()}")
        self.receiver.start(host, self.current_port())
        self._refresh()
        self._update_state()
        self.sessionChanged.emit()

    def _done(self) -> None:
        self.receiver.stop()          # delivers anything still buffered before the CSV closes
        self.collector.done()
        self.logMessage.emit("info", f"Kolektor done: {self.collector.batch} - {len(self.collector.rows)} data, "
                                     f"{self.collector.duplicates} duplikat diabaikan")
        self._dirty = True
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
        result = self.collector.add(text)
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
        error = bool(self.collector.write_error)
        if error != self._error_shown:
            self._error_shown = error
            self.file_label.setStyleSheet(f"color: {theme.RED}; font-weight: 600;" if error else "")
        if error:
            self.file_label.setText(f"Gagal menulis CSV: {self.collector.write_error}")
        elif self.collector.csv_path:
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
        self.host_edit.setEnabled(not active)
        self.port_spin.setEnabled(not active)
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
        if not active:
            self.conn_label.setText("●  TCP/IP tidak tersambung")
            self.conn_label.setToolTip("")
            self.conn_label.setStyleSheet(f"color: {theme.MUTED}; font-weight: 600;")
        self._refresh()
