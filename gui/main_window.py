"""Main window of FTP Photo Renamer."""
from __future__ import annotations

import html
import ipaddress
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QRegularExpression, Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QColor, QDesktopServices, QFontDatabase, QRegularExpressionValidator
from PySide6.QtNetwork import QAbstractSocket, QNetworkInterface
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

import app_config
import naming
from backend_client import BackendClient, find_backend
from photo_preview import PhotoPreview

# Only the newest rows/lines are kept on screen so the UI stays light when running
# continuously; the full data is in the daily txt files in <folder tujuan>\_log.
MAX_TABLE_ROWS = 50
MAX_LOG_LINES = 50

STATUS_TEXT = {
    "saved": ("Disimpan", "#1e8e3e"),
    "duplicate": ("Duplikat (dibuang)", "#d97706"),
    "unmatched": ("Format tidak sesuai", "#64748b"),
    "error": ("Gagal", "#dc2626"),
}

STATE_STYLE = {
    "stopped": ("Berhenti", "#64748b"),
    "starting": ("Memulai...", "#d97706"),
    "running": ("Berjalan", "#1e8e3e"),
    "stopping": ("Menghentikan...", "#d97706"),
}

LOG_COLORS = {"warn": "#d97706", "error": "#dc2626"}


def local_ipv4_addresses() -> list[str]:
    found: list[str] = []
    for address in QNetworkInterface.allAddresses():
        if address.protocol() == QAbstractSocket.NetworkLayerProtocol.IPv4Protocol:
            text = address.toString()
            if text not in found:
                found.append(text)
    return found


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("FTP Photo Renamer")
        self.resize(1280, 860)

        self.cfg = app_config.load()
        self._state = "stopped"
        self._stop_requested = False
        self._last_error: str | None = None
        self._running_line_id = ""
        self._counts = {k: 0 for k in ("received", "saved", "duplicate", "unmatched", "error")}
        self._counts_connections = 0
        self._link_up: bool | None = None

        self.backend = BackendClient(self)
        self.backend.event_received.connect(self._on_event)
        self.backend.output_text.connect(self._append_log)
        self.backend.finished.connect(self._on_backend_finished)

        self._build_ui()
        self._apply_config(self.cfg)
        self._set_state("stopped")
        self._refresh_counts()
        self._update_preview()

        if self.cfg.get("autostart"):
            QTimer.singleShot(300, self.start_server)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)
        top.addWidget(self._build_connection_group(), 1)
        top.addWidget(self._build_naming_group(), 1)
        root.addLayout(top)
        root.addLayout(self._build_control_row())
        root.addLayout(self._build_stats_row())
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_tabs())
        self.preview = PhotoPreview()
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([760, 480])
        root.addWidget(splitter, 1)

        self.setCentralWidget(central)

    def _build_connection_group(self) -> QGroupBox:
        box = QGroupBox("Koneksi FTP")
        layout = QVBoxLayout(box)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode koneksi:"))
        self.mode_server = QRadioButton("Server  (kamera kirim ke aplikasi ini)")
        self.mode_client = QRadioButton("Client  (ambil dari server FTP)")
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.mode_server, 0)
        self.mode_group.addButton(self.mode_client, 1)
        self.mode_server.setChecked(True)
        mode_row.addWidget(self.mode_server)
        mode_row.addWidget(self.mode_client)
        mode_row.addStretch(1)
        layout.addLayout(mode_row)

        self.mode_stack = QStackedWidget()
        self.mode_stack.addWidget(self._build_server_page())
        self.mode_stack.addWidget(self._build_client_page())
        layout.addWidget(self.mode_stack, 1)

        self.mode_group.idToggled.connect(self._on_mode_toggled)
        self._mode_widgets = [self.mode_server, self.mode_client]
        return box

    def _build_server_page(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnStretch(1, 1)

        self.ip_combo = QComboBox()
        self.ip_combo.setEditable(True)
        self.ip_combo.addItem("0.0.0.0")
        for ip in local_ipv4_addresses():
            self.ip_combo.addItem(ip)
        self.ip_combo.setToolTip("0.0.0.0 = terima koneksi dari semua kartu jaringan komputer ini")

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)

        self.user_edit = QLineEdit()
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.show_pass = QCheckBox("Tampilkan")
        self.show_pass.toggled.connect(
            lambda on: self.pass_edit.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password)
        )

        self.any_login = QCheckBox("Terima username/password apa saja")
        self.any_login.toggled.connect(self._update_enabled)

        self.pasv_min = QSpinBox()
        self.pasv_max = QSpinBox()
        for spin in (self.pasv_min, self.pasv_max):
            spin.setRange(0, 65535)
            spin.setToolTip("Rentang port data (mode pasif). 0 = otomatis.")

        grid.addWidget(QLabel("IP lokal"), 0, 0)
        grid.addWidget(self.ip_combo, 0, 1)
        grid.addWidget(QLabel("Port"), 0, 2)
        grid.addWidget(self.port_spin, 0, 3)

        grid.addWidget(QLabel("Username"), 1, 0)
        grid.addWidget(self.user_edit, 1, 1, 1, 3)

        pass_row = QHBoxLayout()
        pass_row.addWidget(self.pass_edit, 1)
        pass_row.addWidget(self.show_pass)
        grid.addWidget(QLabel("Password"), 2, 0)
        grid.addLayout(pass_row, 2, 1, 1, 3)

        grid.addWidget(self.any_login, 3, 1, 1, 3)

        pasv_row = QHBoxLayout()
        pasv_row.addWidget(self.pasv_min)
        pasv_row.addWidget(QLabel("s/d"))
        pasv_row.addWidget(self.pasv_max)
        pasv_row.addStretch(1)
        grid.addWidget(QLabel("Port pasif"), 4, 0)
        grid.addLayout(pasv_row, 4, 1, 1, 3)

        hint = QLabel("Kamera mengirim foto ke aplikasi ini. Isi IP komputer ini, port, username "
                      "dan password yang sama di setting FTP kamera.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid);")
        grid.addWidget(hint, 5, 0, 1, 4)
        grid.setRowStretch(6, 1)

        self._server_widgets = [
            self.ip_combo, self.port_spin, self.user_edit, self.pass_edit, self.any_login,
            self.pasv_min, self.pasv_max,
        ]
        return page

    def _build_client_page(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnStretch(1, 1)

        self.c_host_edit = QLineEdit()
        self.c_host_edit.setPlaceholderText("contoh: 192.168.1.100")
        self.c_port_spin = QSpinBox()
        self.c_port_spin.setRange(1, 65535)
        self.c_user_edit = QLineEdit()
        self.c_pass_edit = QLineEdit()
        self.c_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        c_show_pass = QCheckBox("Tampilkan")
        c_show_pass.toggled.connect(
            lambda on: self.c_pass_edit.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password)
        )
        self.c_dir_edit = QLineEdit()
        self.c_dir_edit.setPlaceholderText("/")
        self.c_dir_edit.setToolTip("Folder di server FTP tempat foto berada, contoh: / atau /kamera1")
        self.c_recursive = QCheckBox("Termasuk subfolder")
        self.c_interval = QSpinBox()
        self.c_interval.setRange(1, 3600)
        self.c_interval.setSuffix(" detik")
        self.c_interval.setToolTip("Seberapa sering folder di server dicek untuk foto baru")
        self.c_workers = QSpinBox()
        self.c_workers.setRange(1, 16)
        self.c_workers.setToolTip("Jumlah koneksi download paralel (multi proses)")
        self.c_delete = QCheckBox("Hapus file di server setelah berhasil diambil")

        grid.addWidget(QLabel("IP server"), 0, 0)
        grid.addWidget(self.c_host_edit, 0, 1)
        grid.addWidget(QLabel("Port"), 0, 2)
        grid.addWidget(self.c_port_spin, 0, 3)

        grid.addWidget(QLabel("Username"), 1, 0)
        grid.addWidget(self.c_user_edit, 1, 1, 1, 3)

        pass_row = QHBoxLayout()
        pass_row.addWidget(self.c_pass_edit, 1)
        pass_row.addWidget(c_show_pass)
        grid.addWidget(QLabel("Password"), 2, 0)
        grid.addLayout(pass_row, 2, 1, 1, 3)

        grid.addWidget(QLabel("Folder remote"), 3, 0)
        grid.addWidget(self.c_dir_edit, 3, 1)
        grid.addWidget(self.c_recursive, 3, 2, 1, 2)

        timing_row = QHBoxLayout()
        timing_row.addWidget(self.c_interval)
        timing_row.addSpacing(12)
        timing_row.addWidget(QLabel("Download paralel"))
        timing_row.addWidget(self.c_workers)
        timing_row.addStretch(1)
        grid.addWidget(QLabel("Cek setiap"), 4, 0)
        grid.addLayout(timing_row, 4, 1, 1, 3)

        grid.addWidget(self.c_delete, 5, 1, 1, 3)

        hint = QLabel("Aplikasi login ke server FTP, mengambil foto baru secara berkala, lalu rename "
                      "ke folder tujuan. File yang sudah diambil tidak diunduh ulang.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid);")
        grid.addWidget(hint, 6, 0, 1, 4)
        grid.setRowStretch(7, 1)

        self._client_widgets = [
            self.c_host_edit, self.c_port_spin, self.c_user_edit, self.c_pass_edit, c_show_pass,
            self.c_dir_edit, self.c_recursive, self.c_interval, self.c_workers, self.c_delete,
        ]
        return page

    def _build_naming_group(self) -> QGroupBox:
        box = QGroupBox("Penamaan && Penyimpanan")
        grid = QGridLayout(box)
        grid.setColumnStretch(1, 1)

        self.line_edit = QLineEdit()
        self.line_edit.setMaxLength(64)
        self.line_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r'[^\\/:*?"<>|\s]*'), self))
        self.line_edit.setPlaceholderText("contoh: 00001")
        self.line_edit.textChanged.connect(self._update_preview)
        self.line_edit.editingFinished.connect(self._apply_line_id_live)

        self.target_edit = QLineEdit()
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse_target)
        self.open_btn = QPushButton("Buka")
        self.open_btn.setToolTip("Buka folder tujuan di Explorer")
        self.open_btn.clicked.connect(self._open_target)

        self.dedup_check = QCheckBox("Code sama hanya disimpan 1 file (duplikat dibuang)")
        self.dedup_check.toggled.connect(self._update_enabled)
        self.dedup_spin = QSpinBox()
        self.dedup_spin.setRange(0, 525600)
        self.dedup_spin.setSuffix(" menit")
        self.dedup_spin.setSpecialValueText("Selamanya")
        self.dedup_spin.setToolTip(
            "Selamanya (0): code yang sudah pernah disimpan tidak akan disimpan lagi.\n"
            "N menit: code yang sama boleh disimpan lagi setelah lewat N menit."
        )
        self.keep_dup_check = QCheckBox('Simpan duplikat ke subfolder "_duplikat" (tidak dibuang)')
        self.keep_unmatched_check = QCheckBox('Simpan foto yang formatnya tidak sesuai ke "_tidak_sesuai"')
        self.keep_unmatched_check.setToolTip(
            "Tidak dicentang (disarankan): foto tidak disimpan, nama file hanya dicatat di\n"
            "_log\\tidak_sesuai_YYYY-MM-DD.txt supaya tidak memakan ruang hardisk."
        )
        self.keep_unmatched_check.toggled.connect(self._update_preview)
        log_btn = QPushButton("Buka log txt")
        log_btn.setToolTip("Buka folder _log berisi daftar file yang formatnya tidak sesuai")
        log_btn.clicked.connect(self._open_log_dir)

        self.test_edit = QLineEdit(naming.EXAMPLE_INCOMING)
        self.test_edit.setToolTip("Ketik/tempel nama file dari kamera untuk melihat hasil rename")
        self.test_edit.textChanged.connect(self._update_preview)
        self.preview_label = QLabel()
        self.preview_label.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.preview_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        grid.addWidget(QLabel("LINE-ID"), 0, 0)
        grid.addWidget(self.line_edit, 0, 1, 1, 3)

        grid.addWidget(QLabel("Folder tujuan"), 1, 0)
        grid.addWidget(self.target_edit, 1, 1)
        grid.addWidget(browse, 1, 2)
        grid.addWidget(self.open_btn, 1, 3)

        grid.addWidget(self.dedup_check, 2, 1, 1, 3)
        dedup_row = QHBoxLayout()
        dedup_row.addWidget(QLabel("Rentang cek duplikat:"))
        dedup_row.addWidget(self.dedup_spin)
        dedup_row.addStretch(1)
        grid.addLayout(dedup_row, 3, 1, 1, 3)
        grid.addWidget(self.keep_dup_check, 4, 1, 1, 3)
        grid.addWidget(self.keep_unmatched_check, 5, 1, 1, 2)
        grid.addWidget(log_btn, 5, 3)

        grid.addWidget(QLabel("Uji nama file"), 6, 0)
        grid.addWidget(self.test_edit, 6, 1, 1, 3)
        grid.addWidget(QLabel("Hasil rename"), 7, 0)
        grid.addWidget(self.preview_label, 7, 1, 1, 3)
        grid.setRowStretch(8, 1)

        self._naming_widgets = [
            self.target_edit, browse, self.dedup_check, self.dedup_spin, self.keep_dup_check, self.keep_unmatched_check,
        ]
        return box

    def _build_control_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.start_btn = QPushButton("Mulai Server")
        self.start_btn.setMinimumHeight(34)
        self.start_btn.setStyleSheet(
            "QPushButton { background:#1e8e3e; color:white; font-weight:600; padding:0 18px; border-radius:4px; }"
            "QPushButton:disabled { background:#9ca3af; }"
        )
        self.start_btn.clicked.connect(self.start_server)

        self.stop_btn = QPushButton("Stop Server")
        self.stop_btn.setMinimumHeight(34)
        self.stop_btn.setStyleSheet(
            "QPushButton { background:#dc2626; color:white; font-weight:600; padding:0 18px; border-radius:4px; }"
            "QPushButton:disabled { background:#9ca3af; }"
        )
        self.stop_btn.clicked.connect(self.stop_server)

        self.state_label = QLabel()
        self.state_label.setMinimumWidth(130)
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.autostart_check = QCheckBox("Mulai otomatis saat aplikasi dibuka")

        row.addWidget(self.start_btn)
        row.addWidget(self.stop_btn)
        row.addWidget(self.state_label)
        row.addStretch(1)
        row.addWidget(self.autostart_check)
        return row

    def _build_stats_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.stat_labels: dict[str, QLabel] = {}
        for key, title in (
            ("received", "Diterima"),
            ("saved", "Disimpan"),
            ("duplicate", "Duplikat"),
            ("unmatched", "Tidak sesuai"),
            ("error", "Gagal"),
            ("connections", "Koneksi aktif"),
        ):
            label = QLabel()
            label.setStyleSheet("padding:4px 10px; border:1px solid palette(mid); border-radius:4px;")
            label.setProperty("title", title)
            self.stat_labels[key] = label
            row.addWidget(label)
        row.addStretch(1)
        clear = QPushButton("Bersihkan tampilan")
        clear.clicked.connect(self._clear_view)
        row.addWidget(clear)
        return row

    def _build_tabs(self) -> QTabWidget:
        tabs = QTabWidget()

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Waktu", "Dari", "Nama asli (FTP)", "Nama baru", "Code", "Status"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        for col, mode in enumerate((
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.Stretch,
            QHeaderView.ResizeMode.Stretch,
            QHeaderView.ResizeMode.ResizeToContents,
            QHeaderView.ResizeMode.ResizeToContents,
        )):
            header.setSectionResizeMode(col, mode)
        self.table.setToolTip("Klik dua kali untuk membuka foto")
        self.table.cellDoubleClicked.connect(self._open_row_file)
        tabs.addTab(self.table, f"File diterima ({MAX_TABLE_ROWS} terbaru)")

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(MAX_LOG_LINES)
        self.log_view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        tabs.addTab(self.log_view, f"Log ({MAX_LOG_LINES} terbaru)")
        full_data = "Data lengkap per hari ada di folder tujuan\\_log:\n" \
                    "diterima_YYYY-MM-DD.txt, log_YYYY-MM-DD.txt, tidak_sesuai_YYYY-MM-DD.txt"
        tabs.setTabToolTip(0, full_data)
        tabs.setTabToolTip(1, full_data)
        return tabs

    # ------------------------------------------------------------- config
    def _apply_config(self, cfg: dict) -> None:
        (self.mode_client if cfg["mode"] == "client" else self.mode_server).setChecked(True)
        self.c_host_edit.setText(cfg["client_host"])
        self.c_port_spin.setValue(cfg["client_port"])
        self.c_user_edit.setText(cfg["client_user"])
        self.c_pass_edit.setText(cfg["client_password"])
        self.c_dir_edit.setText(cfg["client_remote_dir"])
        self.c_recursive.setChecked(cfg["client_recursive"])
        self.c_interval.setValue(cfg["client_interval"])
        self.c_workers.setValue(cfg["client_workers"])
        self.c_delete.setChecked(cfg["client_delete_after"])
        self.ip_combo.setCurrentText(cfg["ip"])
        self.port_spin.setValue(cfg["port"])
        self.user_edit.setText(cfg["username"])
        self.pass_edit.setText(cfg["password"])
        self.any_login.setChecked(cfg["any_login"])
        self.pasv_min.setValue(cfg["pasv_min"])
        self.pasv_max.setValue(cfg["pasv_max"])
        self.line_edit.setText(cfg["line_id"])
        self.target_edit.setText(cfg["target_dir"])
        self.dedup_check.setChecked(cfg["dedup"])
        self.dedup_spin.setValue(cfg["dedup_minutes"])
        self.keep_dup_check.setChecked(cfg["keep_duplicates"])
        self.keep_unmatched_check.setChecked(cfg["keep_unmatched"])
        self.autostart_check.setChecked(cfg["autostart"])

    def _mode(self) -> str:
        return "client" if self.mode_client.isChecked() else "server"

    def _collect_config(self) -> dict:
        return {
            "mode": self._mode(),
            "client_host": self.c_host_edit.text().strip(),
            "client_port": self.c_port_spin.value(),
            "client_user": self.c_user_edit.text().strip(),
            "client_password": self.c_pass_edit.text(),
            "client_remote_dir": self.c_dir_edit.text().strip() or "/",
            "client_recursive": self.c_recursive.isChecked(),
            "client_interval": self.c_interval.value(),
            "client_workers": self.c_workers.value(),
            "client_delete_after": self.c_delete.isChecked(),
            "ip": self.ip_combo.currentText().strip(),
            "port": self.port_spin.value(),
            "username": self.user_edit.text().strip(),
            "password": self.pass_edit.text(),
            "any_login": self.any_login.isChecked(),
            "pasv_min": self.pasv_min.value(),
            "pasv_max": self.pasv_max.value(),
            "line_id": self.line_edit.text().strip(),
            "target_dir": self.target_edit.text().strip(),
            "dedup": self.dedup_check.isChecked(),
            "dedup_minutes": self.dedup_spin.value(),
            "keep_duplicates": self.keep_dup_check.isChecked(),
            "keep_unmatched": self.keep_unmatched_check.isChecked(),
            "autostart": self.autostart_check.isChecked(),
        }

    def _validate(self, cfg: dict) -> list[str]:
        problems = []
        if not naming.clean_line_id(cfg["line_id"]):
            problems.append("LINE-ID belum diisi.")
        if not cfg["target_dir"]:
            problems.append("Folder tujuan belum dipilih.")
        if cfg["mode"] == "client":
            host = cfg["client_host"]
            if not host or any(c.isspace() for c in host):
                problems.append(f"IP server FTP tidak valid: {host or '(kosong)'}")
            if not cfg["client_user"]:
                problems.append("Username server FTP belum diisi (pakai 'anonymous' jika tanpa login).")
            return problems
        try:
            ipaddress.IPv4Address(cfg["ip"])
        except ValueError:
            problems.append(f"IP Address tidak valid: {cfg['ip'] or '(kosong)'}")
        if not cfg["any_login"] and not cfg["username"]:
            problems.append("Username belum diisi (atau centang 'Terima username/password apa saja').")
        if cfg["pasv_min"] and cfg["pasv_max"] < cfg["pasv_min"]:
            problems.append("Port pasif: nilai akhir harus lebih besar dari nilai awal.")
        if cfg["pasv_min"] and cfg["pasv_min"] <= cfg["port"] <= cfg["pasv_max"]:
            problems.append("Port FTP tidak boleh berada di dalam rentang port pasif.")
        return problems

    # ------------------------------------------------------------ actions
    def start_server(self) -> None:
        if self.backend.is_running():
            return
        cfg = self._collect_config()
        problems = self._validate(cfg)
        if problems:
            QMessageBox.warning(self, "Pengaturan belum benar", "\n".join(problems))
            return
        try:
            Path(cfg["target_dir"]).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            QMessageBox.warning(self, "Folder tujuan", f"Folder tujuan tidak bisa dibuat:\n{exc}")
            return
        try:
            program = find_backend()
        except FileNotFoundError as exc:
            QMessageBox.critical(self, "Backend tidak ditemukan", str(exc))
            return

        self.cfg = cfg
        app_config.save(cfg)

        args = [
            "--target", cfg["target_dir"],
            "--line-id", cfg["line_id"],
            "--dedup-minutes", str(cfg["dedup_minutes"]),
        ]
        if cfg["mode"] == "client":
            password = cfg["client_password"]
            args += [
                "--mode", "client",
                "--ip", cfg["client_host"],
                "--port", str(cfg["client_port"]),
                "--user", cfg["client_user"],
                "--remote-dir", cfg["client_remote_dir"],
                "--interval", str(cfg["client_interval"]),
                "--workers", str(cfg["client_workers"]),
            ]
            if cfg["client_recursive"]:
                args.append("--recursive")
            if cfg["client_delete_after"]:
                args.append("--delete-after")
        else:
            password = cfg["password"]
            args += [
                "--mode", "server",
                "--ip", cfg["ip"],
                "--port", str(cfg["port"]),
                "--user", cfg["username"],
                "--pasv-min", str(cfg["pasv_min"]),
                "--pasv-max", str(cfg["pasv_max"]),
            ]
            if cfg["any_login"]:
                args.append("--any-login")
        if not cfg["dedup"]:
            args.append("--no-dedup")
        if cfg["keep_duplicates"]:
            args.append("--keep-duplicates")
        if cfg["keep_unmatched"]:
            args.append("--keep-unmatched")

        self._stop_requested = False
        self._last_error = None
        self._running_line_id = naming.clean_line_id(cfg["line_id"])
        self._link_up = None
        self._set_state("starting")
        self._append_log("info", f"Menjalankan backend ({cfg['mode']}): {program}")
        self.backend.start(program, args, password)

    def stop_server(self) -> None:
        if not self.backend.is_running():
            return
        self._stop_requested = True
        self._set_state("stopping")
        self.backend.stop()

    def _apply_line_id_live(self) -> None:
        value = naming.clean_line_id(self.line_edit.text())
        if self._state == "running" and value and value != self._running_line_id:
            self._running_line_id = value
            self.backend.send(f"SET LINEID {value}")
            self.cfg["line_id"] = value
            app_config.save(self._collect_config())

    def _browse_target(self) -> None:
        start = self.target_edit.text().strip() or str(Path.home())
        folder = QFileDialog.getExistingDirectory(self, "Pilih folder penyimpanan foto", start)
        if folder:
            self.target_edit.setText(str(Path(folder)))

    def _open_target(self) -> None:
        folder = Path(self.target_edit.text().strip())
        if not folder.is_dir():
            QMessageBox.information(self, "Folder tujuan", "Folder belum ada. Folder akan dibuat saat dimulai.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _open_log_dir(self) -> None:
        folder = Path(self.target_edit.text().strip()) / "_log"
        if not folder.is_dir():
            QMessageBox.information(self, "Log txt", "Belum ada file dengan format tidak sesuai yang dicatat.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _open_row_file(self, row: int, _col: int) -> None:
        item = self.table.item(row, 3)
        path = item.data(Qt.ItemDataRole.UserRole) if item else None
        if path and Path(path).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _clear_view(self) -> None:
        self.table.setRowCount(0)
        self.log_view.clear()
        for key in self._counts:
            self._counts[key] = 0
        self._refresh_counts()

    # ------------------------------------------------------------ backend
    def _on_event(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "state":
            state = event.get("state")
            if state in ("listening", "running"):
                self._set_state("running")
            elif state == "error":
                # the backend also sends the message as a log line
                self._last_error = event.get("message") or "Kesalahan tidak diketahui"
        elif kind == "log":
            self._append_log(event.get("level", "info"), event.get("message", ""), event.get("time"))
        elif kind == "file":
            self._on_file_event(event)
        elif kind == "connections":
            self._counts_connections = int(event.get("count", 0))
            self._refresh_counts()
        elif kind == "link":
            self._link_up = bool(event.get("connected"))
            if self._state == "running":
                self._set_state("running")

    def _on_file_event(self, event: dict) -> None:
        status = event.get("status", "error")
        if event.get("source") in ("upload", "download"):
            self._counts["received"] += 1
        if event.get("previous") == "unmatched" and self._counts["unmatched"] > 0:
            self._counts["unmatched"] -= 1
        if status in self._counts:
            self._counts[status] += 1
        self._refresh_counts()

        text, color = STATUS_TEXT.get(status, (status, "#dc2626"))
        time_text = (event.get("time") or "")[-8:]
        values = [
            time_text,
            event.get("client") or "",
            event.get("original") or "",
            event.get("name") or "",
            event.get("code") or "",
            text,
        ]
        self.table.insertRow(0)
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            if col in (2, 3) and value:
                item.setToolTip(value)
            if col == 5:
                item.setForeground(QColor(color))
                if event.get("message"):
                    item.setToolTip(event["message"])
            self.table.setItem(0, col, item)
        name_item = self.table.item(0, 3)
        if event.get("path"):
            name_item.setData(Qt.ItemDataRole.UserRole, event["path"])
            name_item.setToolTip(event["path"])
        while self.table.rowCount() > MAX_TABLE_ROWS:
            self.table.removeRow(self.table.rowCount() - 1)

        original = event.get("original") or "?"
        if status == "saved" and event.get("path"):
            self.preview.show_saved(event)
        if status == "saved":
            self._append_log("info", f"Disimpan: {original}  ->  {event.get('name')}", event.get("time"))
        elif status == "duplicate":
            where = "disimpan ke _duplikat" if event.get("path") else "dibuang"
            self._append_log("warn", f"Duplikat code {event.get('code')}: {original} ({where})", event.get("time"))
        elif status == "unmatched":
            where = "disimpan ke _tidak_sesuai" if event.get("path") else "foto tidak disimpan, dicatat di _log"
            self._append_log("warn", f"Format nama tidak sesuai: {original} ({where})", event.get("time"))
        else:
            self._append_log("error", f"Gagal: {original} - {event.get('message')}", event.get("time"))

    def _on_backend_finished(self, exit_code: int) -> None:
        self._counts_connections = 0
        self._set_state("stopped")
        self._refresh_counts()
        if self._last_error:
            message, self._last_error = self._last_error, None
            QMessageBox.critical(self, f"{self._mode().capitalize()} tidak bisa berjalan", message)
        elif not self._stop_requested and exit_code != 0:
            self._append_log("error", f"Backend berhenti tiba-tiba (kode {exit_code}).")
        self._append_log("info", f"{self._mode().capitalize()} berhenti.")

    # ------------------------------------------------------------ helpers
    def _on_mode_toggled(self, button_id: int, checked: bool) -> None:
        if checked:
            self.mode_stack.setCurrentIndex(button_id)
            self._set_state(self._state)

    def _state_display(self) -> tuple[str, str]:
        if self._state == "running" and self._mode() == "client":
            return ("Terhubung", "#1e8e3e") if self._link_up else ("Menghubungkan...", "#d97706")
        return STATE_STYLE[self._state]

    def _set_state(self, state: str) -> None:
        self._state = state
        mode_name = self._mode().capitalize()
        self.start_btn.setText(f"Mulai {mode_name}")
        self.stop_btn.setText(f"Stop {mode_name}")
        text, color = self._state_display()
        self.state_label.setText(f"\u25cf  {text}")
        self.state_label.setStyleSheet(
            f"color:{color}; border:1px solid {color}; font-weight:600; padding:6px 12px; border-radius:14px;"
        )
        idle = state == "stopped"
        self.start_btn.setEnabled(idle)
        self.stop_btn.setEnabled(state in ("running", "starting"))
        self._update_enabled()

    def _update_enabled(self) -> None:
        idle = self._state == "stopped"
        for widget in self._mode_widgets + self._server_widgets + self._client_widgets + self._naming_widgets:
            widget.setEnabled(idle)
        if idle:
            self.user_edit.setEnabled(not self.any_login.isChecked())
            self.pass_edit.setEnabled(not self.any_login.isChecked())
            dedup = self.dedup_check.isChecked()
            self.dedup_spin.setEnabled(dedup)
            self.keep_dup_check.setEnabled(dedup)

    def _refresh_counts(self) -> None:
        values = dict(self._counts, connections=self._counts_connections)
        for key, label in self.stat_labels.items():
            label.setText(f"{label.property('title')}: <b>{values[key]}</b>")

    def _update_preview(self) -> None:
        line_id = naming.clean_line_id(self.line_edit.text()) or "?????"
        result = naming.build_name(self.test_edit.text(), line_id)
        if result:
            self.preview_label.setText(result)
            self.preview_label.setStyleSheet("color:#1e8e3e; font-weight:600;")
        else:
            if self.keep_unmatched_check.isChecked():
                self.preview_label.setText("Format tidak sesuai -> masuk ke _tidak_sesuai")
            else:
                self.preview_label.setText("Format tidak sesuai -> tidak disimpan, dicatat di log txt")
            self.preview_label.setStyleSheet("color:#dc2626;")

    def _append_log(self, level: str, message: str, time_text: str | None = None) -> None:
        stamp = time_text or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = html.escape(f"[{stamp}] {message}")
        color = LOG_COLORS.get(level)
        self.log_view.appendHtml(f'<span style="color:{color}">{line}</span>' if color else line)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt API)
        if self.backend.is_running():
            answer = QMessageBox.question(
                self, "Keluar", f"{self._mode().capitalize()} FTP masih berjalan. Hentikan dan keluar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._stop_requested = True
            self.backend.stop_blocking()
        app_config.save(self._collect_config())
        event.accept()
