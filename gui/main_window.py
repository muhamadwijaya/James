"""FRT Cam - main window (sidebar + dashboard)."""
from __future__ import annotations

import html
import ipaddress
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QRegularExpression, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QPainter, QRadialGradient, QRegularExpressionValidator
from PySide6.QtNetwork import QAbstractSocket, QNetworkInterface
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

import app_config
import icons
import naming
import theme
from backend_client import BackendClient, find_backend
from collector import Collector
from collector_page import CollectorPage
from photo_panel import PhotoPanel
from received_table import FileTableCard, ReceivedFilter, ReceivedModel, TableController
from stats import Stats
from widgets import ActivityChart, Card, IconBox, StateBadge, StatCard, StatusBox, TransferCard, qcolor

APP_TITLE = "FRT Cam"
APP_VERSION = "2.0.0"
# Only the newest rows/lines are kept on screen so the UI stays light when running
# continuously; the full data is in the daily txt files in <folder tujuan>\_log.
MAX_TABLE_ROWS = 50
MAX_LOG_LINES = 50
LABEL_WIDTH = 88
DEDUP_CHOICES = [("Selamanya", 0), ("1 menit", 1), ("5 menit", 5), ("10 menit", 10), ("30 menit", 30),
                 ("1 jam", 60), ("2 jam", 120), ("6 jam", 360), ("12 jam", 720), ("24 jam", 1440)]
LOG_COLORS = {"warn": theme.ORANGE, "error": theme.RED}
RESIZE_MARGIN = 6


def local_ipv4_addresses() -> list[str]:
    found: list[str] = []
    for address in QNetworkInterface.allAddresses():
        if address.protocol() == QAbstractSocket.NetworkLayerProtocol.IPv4Protocol:
            text = address.toString()
            if text not in found:
                found.append(text)
    return found


def form_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("formLabel")
    label.setFixedWidth(LABEL_WIDTH)
    return label


def shrinkable(widget: QWidget) -> QWidget:
    """Let long labels/check boxes give up width on small windows (full text stays in the tooltip)."""
    widget.setSizePolicy(QSizePolicy.Policy.Ignored, widget.sizePolicy().verticalPolicy())
    widget.setMinimumWidth(120)
    if not widget.toolTip():
        widget.setToolTip(widget.text())
    return widget


def icon_button(text: str, icon_name: str, color: str = theme.TEXT) -> QPushButton:
    b = QPushButton(text)
    b.setIcon(icons.icon(icon_name, color, 16))
    b.setIconSize(QSize(16, 16))
    return b


class _RootFrame(QWidget):
    """Window background; its thin outer margin resizes the frameless window."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__()
        self.setObjectName("rootFrame")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMouseTracking(True)
        self._window = window

    def _edges(self, pos) -> Qt.Edge:
        edges = Qt.Edge(0)
        if self._window.isMaximized():
            return edges
        if pos.x() <= RESIZE_MARGIN:
            edges |= Qt.Edge.LeftEdge
        if pos.x() >= self.width() - RESIZE_MARGIN:
            edges |= Qt.Edge.RightEdge
        if pos.y() <= RESIZE_MARGIN:
            edges |= Qt.Edge.TopEdge
        if pos.y() >= self.height() - RESIZE_MARGIN:
            edges |= Qt.Edge.BottomEdge
        return edges

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        e = self._edges(event.position().toPoint())
        diag1 = (Qt.Edge.LeftEdge | Qt.Edge.TopEdge, Qt.Edge.RightEdge | Qt.Edge.BottomEdge)
        diag2 = (Qt.Edge.RightEdge | Qt.Edge.TopEdge, Qt.Edge.LeftEdge | Qt.Edge.BottomEdge)
        if e in diag1:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif e in diag2:
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif e & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif e & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        e = self._edges(event.position().toPoint())
        if e and event.button() == Qt.MouseButton.LeftButton and self._window.windowHandle():
            self._window.windowHandle().startSystemResize(e)


class _TitleBar(QWidget):
    """Header area that moves the frameless window; double-click maximizes."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__()
        self.setObjectName("header")
        self._window = window

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._window.windowHandle():
            self._window.windowHandle().startSystemMove()

    def mouseDoubleClickEvent(self, _event) -> None:  # noqa: N802
        self._window.toggle_maximized()


class _Sidebar(QFrame):
    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for cx, cy, radius, alpha in ((0.2, 0.86, 0.9, 0.16), (0.9, 0.98, 0.6, 0.10)):
            g = QRadialGradient(self.width() * cx, self.height() * cy, self.width() * radius)
            g.setColorAt(0, qcolor(theme.BLUE, alpha))
            g.setColorAt(1, qcolor(theme.BLUE, 0.0))
            p.fillRect(self.rect(), g)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_TITLE} - System Rename")
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.resize(1460, 1000)
        self.setMinimumSize(1180, 760)

        self.cfg = app_config.load()
        self._state = "stopped"
        self._stop_requested = False
        self._last_error: str | None = None
        self._running_line_id = ""
        self._running_mode = "server"
        self._running_since: datetime | None = None
        self._link_up: bool | None = None
        self._connections = 0
        self._transfers: dict[int, dict] = {}
        self.stats = Stats()

        self.backend = BackendClient(self)
        self.backend.event_received.connect(self._on_event)
        self.backend.output_text.connect(self._append_log)
        self.backend.finished.connect(self._on_backend_finished)

        self.model = ReceivedModel(MAX_TABLE_ROWS, self)
        self.proxy = ReceivedFilter(self)
        self.proxy.setSourceModel(self.model)
        self.table_ctl = TableController(self.model, self.proxy, self)

        self.collector = Collector()

        self._build_ui()
        self._apply_config(self.cfg)
        self._set_state("stopped")
        self.stats.load_today(self.cfg["target_dir"])
        self._update_preview()
        self._tick()

        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._tick)
        self._ticker.start()

        if self.cfg.get("autostart"):
            QTimer.singleShot(300, self.start_server)

    # ================================================================== UI
    def _build_ui(self) -> None:
        root = _RootFrame(self)
        self._root_layout = QHBoxLayout(root)
        self._root_layout.setContentsMargins(RESIZE_MARGIN, RESIZE_MARGIN, RESIZE_MARGIN, RESIZE_MARGIN)
        self._root_layout.setSpacing(0)

        self.pages = QStackedWidget()
        self._root_layout.addWidget(self._build_sidebar())

        main = QWidget()
        col = QVBoxLayout(main)
        col.setContentsMargins(18, 8, 14, 12)
        col.setSpacing(14)
        col.addWidget(self._build_header())
        self.pages.addWidget(self._build_dashboard_page())
        self.pages.addWidget(self._build_collector_page())
        self.pages.addWidget(self._build_log_page())
        self.pages.addWidget(self._build_files_page())
        self.pages.addWidget(self._build_about_page())
        col.addWidget(self.pages, 1)
        self._root_layout.addWidget(main, 1)
        self.nav_group.idClicked.connect(self.pages.setCurrentIndex)
        self.setCentralWidget(root)

    def _build_sidebar(self) -> QWidget:
        bar = _Sidebar()
        bar.setObjectName("sidebar")
        bar.setFixedWidth(196)
        v = QVBoxLayout(bar)
        v.setContentsMargins(14, 16, 14, 16)
        v.setSpacing(6)

        brand = QHBoxLayout()
        brand.setSpacing(12)
        brand.addWidget(IconBox("camera", theme.BLUE, 42, solid=True, icon_size=24))
        title = QLabel(APP_TITLE)
        title.setObjectName("brandTitle")
        brand.addWidget(title)
        brand.addStretch(1)
        v.addLayout(brand)
        v.addSpacing(22)

        self.nav_group = QButtonGroup(self)
        self.nav_buttons: list[QPushButton] = []
        for i, (text, icon_name) in enumerate((("Dashboard", "home"), ("Kolektor", "grid"),
                                               ("Log Aktivitas", "list"), ("File Diterima", "folder"),
                                               ("Tentang", "info"))):
            b = QPushButton(f"  {text}")
            b.setObjectName("navButton")
            b.setCheckable(True)
            ic = icons.icon(icon_name, "#c9d5e8", 19)
            ic.addPixmap(icons.pixmap(icon_name, "#ffffff", 19), ic.Mode.Normal, ic.State.On)
            b.setIcon(ic)
            b.setIconSize(QSize(19, 19))
            b.setMinimumHeight(44)
            self.nav_group.addButton(b, i)
            self.nav_buttons.append(b)
            v.addWidget(b)
        self.nav_buttons[0].setChecked(True)
        v.addStretch(1)

        version = QFrame()
        version.setObjectName("versionCard")
        vl = QHBoxLayout(version)
        vl.setContentsMargins(12, 12, 12, 12)
        vl.setSpacing(12)
        vl.addWidget(IconBox("camera", theme.BLUE, 36, solid=True, icon_size=20))
        vt = QLabel(f"Versi {APP_VERSION}<br><span style='color:{theme.MUTED}'>{APP_TITLE}</span>")
        vl.addWidget(vt, 1)
        v.addWidget(version)
        return bar

    def _build_header(self) -> QWidget:
        header = _TitleBar(self)
        h = QHBoxLayout(header)
        h.setContentsMargins(0, 4, 0, 0)
        h.setSpacing(14)
        h.addWidget(IconBox("rename", theme.BLUE, 42, solid=False, icon_size=22))
        texts = QVBoxLayout()
        texts.setSpacing(0)
        t = QLabel("System Rename")
        t.setObjectName("headerTitle")
        s = QLabel("Pantau, terima, dan simpan foto dari kamera secara real-time")
        s.setObjectName("headerSubtitle")
        texts.addWidget(t)
        texts.addWidget(s)
        h.addLayout(texts)
        h.addStretch(1)
        self.header_status = StatusBox(compact=True)
        h.addWidget(self.header_status)
        h.addSpacing(20)
        for name, tip, slot, obj in (("minimize", "Minimalkan", self.showMinimized, "windowButton"),
                                     ("maximize", "Maksimalkan", self.toggle_maximized, "windowButton"),
                                     ("close", "Tutup", self.close, "closeButton")):
            b = QPushButton()
            b.setObjectName(obj)
            b.setIcon(icons.icon(name, "#c9d5e8", 18))
            b.setIconSize(QSize(18, 18))
            b.setToolTip(tip)
            b.clicked.connect(slot)
            h.addWidget(b)
            if name == "maximize":
                self._max_button = b
        return header

    # ------------------------------------------------------------ dashboard
    def _build_dashboard_page(self) -> QWidget:
        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(0, 0, 6, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(0, 51)
        grid.setColumnStretch(1, 49)

        grid.addWidget(self._build_connection_card(), 0, 0)
        grid.addWidget(self._build_naming_card(), 0, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(14)
        self.start_btn = QPushButton("Mulai Server")
        self.start_btn.setObjectName("primaryButton")
        self.start_btn.setIcon(icons.icon("play", "#ffffff", 16))
        self.start_btn.setIconSize(QSize(16, 16))
        self.start_btn.clicked.connect(self.start_server)
        self.stop_btn = QPushButton("Stop Server")
        self.stop_btn.setObjectName("dangerButton")
        self.stop_btn.setIcon(icons.icon("stop", "#ffffff", 16))
        self.stop_btn.setIconSize(QSize(16, 16))
        self.stop_btn.clicked.connect(self.stop_server)
        self.state_badge = StateBadge()
        for w in (self.start_btn, self.stop_btn, self.state_badge):
            w.setMinimumHeight(54)
            w.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            buttons.addWidget(w, 1)
        grid.addLayout(buttons, 1, 0)

        live = QHBoxLayout()
        live.setSpacing(14)
        activity = Card(margins=(16, 10, 16, 10))
        head = QHBoxLayout()
        head_label = QLabel("Aktivitas (FTP 1 menit terakhir)")
        head_label.setStyleSheet("font-size: 9pt;")
        head_icon = QLabel()
        head_icon.setPixmap(icons.pixmap("sparkle", theme.MUTED, 14))
        head.addWidget(head_label)
        head.addStretch(1)
        head.addWidget(head_icon)
        activity.body.setSpacing(4)
        activity.body.addLayout(head)
        self.activity_chart = ActivityChart()
        self.activity_chart.setToolTip("Jumlah file diterima per detik")
        activity.body.addWidget(self.activity_chart, 1)
        self.transfer_card = TransferCard()
        live.addWidget(activity, 1)
        live.addWidget(self.transfer_card, 1)
        grid.addLayout(live, 1, 1)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(14)
        self.stat_cards: dict[str, StatCard] = {}
        for key, title, icon_name, color in (
            ("received", "Diterima", "download", theme.BLUE),
            ("saved", "Disimpan", "file_check", theme.GREEN),
            ("duplicate", "Duplikat", "copy", theme.ORANGE),
            ("unmatched", "Tidak sesuai", "file_x", theme.PURPLE),
            ("error", "Gagal", "alert", theme.RED),
            ("connections", "Koneksi aktif", "link", theme.BLUE),
        ):
            card = StatCard(title, icon_name, color)
            self.stat_cards[key] = card
            stats_row.addWidget(card, 1)
        grid.addLayout(stats_row, 2, 0, 1, 2)

        bottom = QHBoxLayout()
        bottom.setSpacing(14)
        self.table_card = FileTableCard(self.table_ctl, f"File Diterima ({MAX_TABLE_ROWS} terbaru)")
        self.table_card.rowActivated.connect(self._show_row)
        self.photo = PhotoPanel()
        bottom.addWidget(self.table_card, 66)
        bottom.addWidget(self.photo, 34)
        grid.addLayout(bottom, 3, 0, 1, 2)
        grid.setRowStretch(3, 1)
        content.setMinimumHeight(900)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(content)
        return scroll

    def _build_connection_card(self) -> Card:
        card = Card("Koneksi", "Atur koneksi ke kamera", "wifi")
        self.conn_status = StatusBox()
        self.conn_status.setMinimumWidth(170)
        settings = QPushButton()
        settings.setObjectName("iconButton")
        settings.setIcon(icons.icon("gear", theme.TEXT, 18))
        settings.setIconSize(QSize(18, 18))
        settings.setFixedSize(38, 38)
        settings.setToolTip("Pengaturan")
        menu = QMenu(settings)
        self.autostart_action = QAction("Mulai otomatis saat aplikasi dibuka", menu)
        self.autostart_action.setCheckable(True)
        self.autostart_action.toggled.connect(lambda _on: app_config.save(self._collect_config()))
        menu.addAction(self.autostart_action)
        menu.addSeparator()
        menu.addAction("Buka folder tujuan", self._open_target)
        menu.addAction("Buka folder log txt", self._open_log_dir)
        settings.setMenu(menu)
        settings.setStyleSheet("QPushButton::menu-indicator { image: none; width: 0; }")
        card.header_right.addWidget(self.conn_status)
        card.header_right.addWidget(settings, 0, Qt.AlignmentFlag.AlignTop)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(18)
        mode_row.addWidget(form_label("Mode koneksi"))
        self.mode_server = QRadioButton("Server (kamera kirim ke aplikasi ini)")
        self.mode_client = QRadioButton("Client (ambil dari server lain)")
        shrinkable(self.mode_server)
        shrinkable(self.mode_client)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.mode_server, 0)
        self.mode_group.addButton(self.mode_client, 1)
        self.mode_server.setChecked(True)
        mode_row.addWidget(self.mode_server, 5)
        mode_row.addWidget(self.mode_client, 4)
        card.body.addLayout(mode_row)

        self.mode_stack = QStackedWidget()
        self.mode_stack.addWidget(self._build_server_page())
        self.mode_stack.addWidget(self._build_client_page())
        card.body.addWidget(self.mode_stack, 1)
        self.mode_group.idToggled.connect(self._on_mode_toggled)
        self._mode_widgets = [self.mode_server, self.mode_client]
        return card

    def _password_field(self) -> tuple[QLineEdit, QCheckBox]:
        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        show = QCheckBox("Tampilkan")
        eye = edit.addAction(icons.icon("eye", theme.MUTED, 16), QLineEdit.ActionPosition.TrailingPosition)
        eye.setToolTip("Tampilkan password")
        eye.triggered.connect(lambda: show.setChecked(not show.isChecked()))

        def apply(on: bool) -> None:
            edit.setEchoMode(QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password)
            eye.setIcon(icons.icon("eye_off" if on else "eye", theme.MUTED, 16))
        show.toggled.connect(apply)
        return edit, show

    def _info_line(self, text: str) -> QWidget:
        w = QWidget()
        row = QHBoxLayout(w)
        row.setContentsMargins(0, 2, 0, 0)
        row.setSpacing(8)
        ic = QLabel()
        ic.setPixmap(icons.pixmap("info", theme.BLUE, 16))
        label = QLabel(text)
        label.setObjectName("hint")
        label.setWordWrap(True)
        row.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(label, 1)
        return w

    def _build_server_page(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(7)
        grid.setColumnStretch(1, 1)

        self.ip_combo = QComboBox()
        self.ip_combo.setEditable(True)
        self.ip_combo.addItem("0.0.0.0")
        for ip in local_ipv4_addresses():
            self.ip_combo.addItem(ip)
        self.ip_combo.setToolTip("0.0.0.0 = terima koneksi dari semua kartu jaringan komputer ini")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setFixedWidth(96)
        self.user_edit = QLineEdit()
        self.pass_edit, self.show_pass = self._password_field()
        self.any_login = QCheckBox("Terima username/password apa saja")
        self.any_login.toggled.connect(self._update_enabled)
        self.pasv_min = QSpinBox()
        self.pasv_max = QSpinBox()
        for spin in (self.pasv_min, self.pasv_max):
            spin.setRange(0, 65535)
            spin.setFixedWidth(100)
            spin.setToolTip("Rentang port data (mode pasif). 0 = otomatis.")

        grid.addWidget(form_label("IP lokal"), 0, 0)
        grid.addWidget(self.ip_combo, 0, 1)
        port_label = QLabel("Port")
        port_label.setObjectName("formLabel")
        grid.addWidget(port_label, 0, 2)
        grid.addWidget(self.port_spin, 0, 3)
        grid.addWidget(form_label("Username"), 1, 0)
        grid.addWidget(self.user_edit, 1, 1, 1, 3)
        grid.addWidget(form_label("Password"), 2, 0)
        grid.addWidget(self.pass_edit, 2, 1, 1, 2)
        grid.addWidget(self.show_pass, 2, 3)
        pasv = QHBoxLayout()
        pasv.setSpacing(10)
        pasv.addWidget(self.pasv_min)
        pasv.addWidget(QLabel("s/d"))
        pasv.addWidget(self.pasv_max)
        pasv.addStretch(1)
        grid.addWidget(form_label("Port pasif"), 3, 0)
        grid.addLayout(pasv, 3, 1, 1, 3)
        grid.addWidget(self.any_login, 4, 1, 1, 3)
        grid.addWidget(self._info_line("Kamera mengirim foto ke aplikasi ini. Isi IP komputer ini, port, username dan "
                                       "password yang sama di setting FTP kamera."), 5, 0, 1, 4)
        grid.setRowStretch(6, 1)
        self._server_widgets = [self.ip_combo, self.port_spin, self.user_edit, self.pass_edit, self.show_pass,
                                self.any_login, self.pasv_min, self.pasv_max]
        return page

    def _build_client_page(self) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(7)
        grid.setColumnStretch(1, 1)

        self.c_host_edit = QLineEdit()
        self.c_host_edit.setPlaceholderText("contoh: 192.168.1.100")
        self.c_port_spin = QSpinBox()
        self.c_port_spin.setRange(1, 65535)
        self.c_port_spin.setFixedWidth(96)
        self.c_user_edit = QLineEdit()
        self.c_pass_edit, c_show = self._password_field()
        self.c_dir_edit = QLineEdit()
        self.c_dir_edit.setPlaceholderText("/")
        self.c_dir_edit.setToolTip("Folder di server FTP tempat foto berada, contoh: / atau /kamera1")
        self.c_recursive = QCheckBox("Termasuk subfolder")
        self.c_interval = QSpinBox()
        self.c_interval.setRange(1, 3600)
        self.c_interval.setSuffix(" detik")
        self.c_interval.setFixedWidth(110)
        self.c_workers = QSpinBox()
        self.c_workers.setRange(1, 16)
        self.c_workers.setFixedWidth(80)
        self.c_workers.setToolTip("Jumlah koneksi download paralel (multi proses)")
        self.c_delete = QCheckBox("Hapus file di server setelah berhasil diambil")

        grid.addWidget(form_label("IP server"), 0, 0)
        grid.addWidget(self.c_host_edit, 0, 1)
        port_label = QLabel("Port")
        port_label.setObjectName("formLabel")
        grid.addWidget(port_label, 0, 2)
        grid.addWidget(self.c_port_spin, 0, 3)
        grid.addWidget(form_label("Username"), 1, 0)
        grid.addWidget(self.c_user_edit, 1, 1, 1, 3)
        grid.addWidget(form_label("Password"), 2, 0)
        grid.addWidget(self.c_pass_edit, 2, 1, 1, 2)
        grid.addWidget(c_show, 2, 3)
        grid.addWidget(form_label("Folder remote"), 3, 0)
        grid.addWidget(self.c_dir_edit, 3, 1)
        grid.addWidget(self.c_recursive, 3, 2, 1, 2)
        timing = QHBoxLayout()
        timing.setSpacing(10)
        timing.addWidget(self.c_interval)
        timing.addSpacing(8)
        timing.addWidget(QLabel("Download paralel"))
        timing.addWidget(self.c_workers)
        timing.addStretch(1)
        grid.addWidget(form_label("Cek setiap"), 4, 0)
        grid.addLayout(timing, 4, 1, 1, 3)
        grid.addWidget(self.c_delete, 5, 1, 1, 3)
        grid.addWidget(self._info_line("Aplikasi login ke server FTP, mengambil foto baru secara berkala, lalu rename ke "
                                       "folder tujuan. File yang sudah diambil tidak diunduh ulang."), 6, 0, 1, 4)
        grid.setRowStretch(7, 1)
        self._client_widgets = [self.c_host_edit, self.c_port_spin, self.c_user_edit, self.c_pass_edit, c_show,
                                self.c_dir_edit, self.c_recursive, self.c_interval, self.c_workers, self.c_delete]
        return page

    def _build_naming_card(self) -> Card:
        card = Card("Penamaan & Penyimpanan", "Atur lokasi penyimpanan dan format nama file", "folder")
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)

        self.line_edit = QLineEdit()
        self.line_edit.setMaxLength(64)
        self.line_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r'[^\\/:*?"<>|\s]*'), self))
        self.line_edit.setPlaceholderText("contoh: 00001")
        self.line_edit.textChanged.connect(self._update_preview)
        self.line_edit.editingFinished.connect(self._apply_line_id_live)
        self.target_edit = QLineEdit()
        self.target_edit.editingFinished.connect(lambda: self.target_edit.setCursorPosition(0))
        browse = icon_button("Browse...", "folder")
        browse.clicked.connect(self._browse_target)
        open_btn = icon_button("Buka", "file_text")
        open_btn.setToolTip("Buka folder tujuan di Explorer")
        open_btn.clicked.connect(self._open_target)

        self.dedup_check = QCheckBox("Code sama hanya disimpan 1 file (duplikat dibuang)")
        self.dedup_check.toggled.connect(self._update_enabled)
        self.dedup_combo = QComboBox()
        for text, minutes in DEDUP_CHOICES:
            self.dedup_combo.addItem(text, minutes)
        self.dedup_combo.setFixedWidth(130)
        help_icon = QLabel()
        help_icon.setPixmap(icons.pixmap("help", theme.MUTED, 16))
        help_icon.setToolTip("Selamanya: code yang sudah pernah disimpan tidak akan disimpan lagi.\n"
                             "Waktu lain: code yang sama boleh disimpan lagi setelah lewat waktu tersebut.")
        self.keep_dup_check = QCheckBox('Simpan duplikat ke subfolder "_duplikat" (tidak dibuang)')
        self.keep_unmatched_check = QCheckBox('Simpan foto yang formatnya tidak sesuai ke "_tidak_sesuai"')
        for box in (self.dedup_check, self.keep_dup_check, self.keep_unmatched_check):
            shrinkable(box)
        self.keep_unmatched_check.setToolTip(
            "Tidak dicentang (disarankan): foto tidak disimpan, nama file hanya dicatat di\n"
            "_log\\tidak_sesuai_YYYY-MM-DD.txt supaya tidak memakan ruang hardisk.")
        self.keep_unmatched_check.toggled.connect(self._update_preview)
        log_btn = icon_button("Buka log txt", "file_text")
        log_btn.setToolTip("Buka folder _log berisi data harian (diterima, log, tidak sesuai)")
        log_btn.clicked.connect(self._open_log_dir)
        self.test_edit = QLineEdit(naming.EXAMPLE_INCOMING)
        self.test_edit.setToolTip("Ketik/tempel nama file dari kamera untuk melihat hasil rename")
        self.test_edit.textChanged.connect(self._update_preview)
        self.preview_label = QLabel()
        self.preview_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        grid.addWidget(form_label("LINE-ID"), 0, 0)
        grid.addWidget(self.line_edit, 0, 1, 1, 3)
        grid.addWidget(form_label("Folder tujuan"), 1, 0)
        grid.addWidget(self.target_edit, 1, 1)
        grid.addWidget(browse, 1, 2)
        grid.addWidget(open_btn, 1, 3)
        grid.addWidget(self.dedup_check, 2, 1, 1, 3)
        dedup_row = QHBoxLayout()
        dedup_row.setSpacing(10)
        dedup_label = QLabel("Rentang cek duplikat")
        dedup_label.setObjectName("formLabel")
        dedup_row.addWidget(dedup_label)
        dedup_row.addWidget(self.dedup_combo)
        dedup_row.addWidget(help_icon)
        dedup_row.addStretch(1)
        grid.addLayout(dedup_row, 3, 1, 1, 3)
        grid.addWidget(self.keep_dup_check, 4, 1, 1, 3)
        grid.addWidget(self.keep_unmatched_check, 5, 1, 1, 2)
        grid.addWidget(log_btn, 5, 3)
        grid.addWidget(form_label("Uji nama file"), 6, 0)
        grid.addWidget(self.test_edit, 6, 1, 1, 3)
        grid.addWidget(form_label("Hasil rename"), 7, 0)
        grid.addWidget(self.preview_label, 7, 1, 1, 3)
        card.body.addLayout(grid)
        card.body.addStretch(1)
        self._naming_widgets = [self.target_edit, browse, self.dedup_check, self.dedup_combo, self.keep_dup_check,
                                self.keep_unmatched_check]
        return card

    # ----------------------------------------------------------- other pages
    def _build_collector_page(self) -> QWidget:
        self.collector_page = CollectorPage(self.collector)
        self.collector_page.sessionChanged.connect(self._on_collector_session)
        return self.collector_page

    def _build_log_page(self) -> QWidget:
        card = Card("Log Aktivitas", f"{MAX_LOG_LINES} baris terbaru. Data lengkap per hari: "
                                     "folder tujuan\\_log\\log_YYYY-MM-DD.txt", "list")
        open_btn = icon_button("Buka log txt", "file_text")
        open_btn.clicked.connect(self._open_log_dir)
        card.header_right.addWidget(open_btn)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(MAX_LOG_LINES)
        card.body.addWidget(self.log_view, 1)
        return card

    def _build_files_page(self) -> QWidget:
        open_btn = icon_button("Buka txt", "file_text")
        open_btn.setToolTip("Data lengkap per hari: folder tujuan\\_log\\diterima_YYYY-MM-DD.txt")
        open_btn.clicked.connect(self._open_log_dir)
        self.files_card = FileTableCard(self.table_ctl, f"File Diterima ({MAX_TABLE_ROWS} terbaru)", (open_btn,))
        self.files_card.rowActivated.connect(self._show_row)
        return self.files_card

    def _build_about_page(self) -> QWidget:
        card = Card("Tentang", f"{APP_TITLE} - System Rename", "info")
        row = QHBoxLayout()
        row.setSpacing(18)
        row.addWidget(IconBox("camera", theme.BLUE, 72, solid=True, icon_size=40), 0, Qt.AlignmentFlag.AlignTop)
        text = QLabel(
            f"<div style='font-size:16pt; font-weight:700'>{APP_TITLE}</div>"
            f"<div style='color:{theme.MUTED}'>Versi {APP_VERSION}</div><br>"
            "Menerima foto dari kamera lewat FTP, mengganti nama menjadi "
            "<b>LINE-ID_YYYYMMDD_HHMMSS_CODE</b>, lalu menyimpannya ke folder tujuan.<br><br>"
            "<b>Fitur</b><ul>"
            "<li>Mode <b>Server</b> (kamera mengirim ke aplikasi) dan <b>Client</b> (ambil dari server FTP lain)</li>"
            "<li>Code yang sama hanya disimpan 1 file</li>"
            "<li>Nama yang tidak sesuai tidak disimpan, cukup dicatat di log txt</li>"
            "<li>Log txt per hari di folder tujuan\\_log: diterima, log, tidak_sesuai</li>"
            "<li>Backend C# multi koneksi, GUI PySide6</li></ul>")
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.RichText)
        row.addWidget(text, 1)
        card.body.addLayout(row)
        card.body.addStretch(1)
        return card

    # ================================================================ config
    def _apply_config(self, cfg: dict) -> None:
        (self.mode_client if cfg["mode"] == "client" else self.mode_server).setChecked(True)
        self.mode_stack.setCurrentIndex(1 if cfg["mode"] == "client" else 0)
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
        self.target_edit.setCursorPosition(0)
        self.dedup_check.setChecked(cfg["dedup"])
        self._set_dedup_minutes(cfg["dedup_minutes"])
        self.keep_dup_check.setChecked(cfg["keep_duplicates"])
        self.keep_unmatched_check.setChecked(cfg["keep_unmatched"])
        self.autostart_action.blockSignals(True)
        self.autostart_action.setChecked(cfg["autostart"])
        self.autostart_action.blockSignals(False)
        collect_folder = cfg["collect_folder"] or str(Path(cfg["target_dir"]) / "collect")
        self.collector_page.set_config(cfg["collect_number"], collect_folder)

    def _set_dedup_minutes(self, minutes: int) -> None:
        index = self.dedup_combo.findData(minutes)
        if index < 0:
            self.dedup_combo.addItem(f"{minutes} menit", minutes)
            index = self.dedup_combo.count() - 1
        self.dedup_combo.setCurrentIndex(index)

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
            "dedup_minutes": int(self.dedup_combo.currentData() or 0),
            "keep_duplicates": self.keep_dup_check.isChecked(),
            "keep_unmatched": self.keep_unmatched_check.isChecked(),
            "autostart": self.autostart_action.isChecked(),
            "collect_number": self.collector_page.current_number(),
            "collect_folder": self.collector_page.current_folder(),
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

    # =============================================================== actions
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
        args = ["--target", cfg["target_dir"], "--line-id", cfg["line_id"], "--dedup-minutes", str(cfg["dedup_minutes"])]
        if cfg["mode"] == "client":
            password = cfg["client_password"]
            args += ["--mode", "client", "--ip", cfg["client_host"], "--port", str(cfg["client_port"]),
                     "--user", cfg["client_user"], "--remote-dir", cfg["client_remote_dir"],
                     "--interval", str(cfg["client_interval"]), "--workers", str(cfg["client_workers"])]
            if cfg["client_recursive"]:
                args.append("--recursive")
            if cfg["client_delete_after"]:
                args.append("--delete-after")
        else:
            password = cfg["password"]
            args += ["--mode", "server", "--ip", cfg["ip"], "--port", str(cfg["port"]), "--user", cfg["username"],
                     "--pasv-min", str(cfg["pasv_min"]), "--pasv-max", str(cfg["pasv_max"])]
            if cfg["any_login"]:
                args.append("--any-login")
        if not cfg["dedup"]:
            args.append("--no-dedup")
        if cfg["keep_duplicates"]:
            args.append("--keep-duplicates")
        if cfg["keep_unmatched"]:
            args.append("--keep-unmatched")

        self.stats.load_today(cfg["target_dir"])
        self._stop_requested = False
        self._last_error = None
        self._running_line_id = naming.clean_line_id(cfg["line_id"])
        self._running_mode = cfg["mode"]
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

    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def changeEvent(self, event) -> None:  # noqa: N802
        if event.type() == event.Type.WindowStateChange and hasattr(self, "_root_layout"):
            m = 0 if self.isMaximized() else RESIZE_MARGIN
            self._root_layout.setContentsMargins(m, m, m, m)
            self._max_button.setIcon(icons.icon("restore" if self.isMaximized() else "maximize", "#c9d5e8", 18))
        super().changeEvent(event)

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
            self.target_edit.setCursorPosition(0)
            self.stats.load_today(self.target_edit.text())

    def _open_target(self) -> None:
        folder = Path(self.target_edit.text().strip())
        if not folder.is_dir():
            QMessageBox.information(self, "Folder tujuan", "Folder belum ada. Folder akan dibuat saat dimulai.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _open_log_dir(self) -> None:
        folder = Path(self.target_edit.text().strip()) / "_log"
        if not folder.is_dir():
            QMessageBox.information(self, "Log txt", "Belum ada log txt di folder tujuan.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _show_row(self, row: dict) -> None:
        path = row.get("path") or ""
        if path and Path(path).exists():
            self.photo.show_event_now(row)
            self.nav_buttons[0].click()
            return
        details = "\n".join(f"{k}: {v}" for k, v in (
            ("Waktu", row.get("time")), ("Dari", row.get("client")), ("Nama asli", row.get("original")),
            ("Nama baru", row.get("name") or "-"), ("Code", row.get("code") or "-"),
            ("Status", row.get("status")), ("Keterangan", row.get("message") or "-")))
        QMessageBox.information(self, "Detail file", details)

    # =============================================================== backend
    def _on_event(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "state":
            state = event.get("state")
            if state in ("listening", "running"):
                self._running_since = datetime.now()
                self._set_state("running")
            elif state == "error":
                # the backend also sends the message as a log line
                self._last_error = event.get("message") or "Kesalahan tidak diketahui"
        elif kind == "log":
            self._append_log(event.get("level", "info"), event.get("message", ""), event.get("time"))
        elif kind == "file":
            self._on_file_event(event)
        elif kind == "transfer":
            self._on_transfer(event)
        elif kind == "connections":
            self._connections = int(event.get("count", 0))
            self._update_stat_cards()
        elif kind == "link":
            self._link_up = bool(event.get("connected"))
            if self._state == "running":
                self._set_state("running")

    def _on_file_event(self, event: dict) -> None:
        self.stats.record(event)
        self.model.add(event)
        self.collector_page.feed_event(event)
        status = event.get("status", "error")
        if status == "saved" and event.get("path"):
            self.photo.show_saved(event)
        original = event.get("original") or "?"
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

    def _on_transfer(self, event: dict) -> None:
        tid = int(event.get("id", 0))
        info = {"name": event.get("new_name") or event.get("name") or "-", "bytes": int(event.get("bytes", 0)),
                "total": int(event.get("total", -1)), "ms": int(event.get("ms", 0)), "state": event.get("state")}
        if info["state"] in ("done", "error"):
            self._transfers.pop(tid, None)
        else:
            self._transfers[tid] = info
        extra = max(0, len(self._transfers) - (0 if info["state"] in ("done", "error") else 1))
        self.transfer_card.set_transfer(info["name"], info["bytes"], info["total"], info["ms"], info["state"], extra)

    def _on_collector_session(self) -> None:
        if not self.collector.active and self.collector.batch:
            # after Done: remember the batch folder and suggest the next number
            import collector as collector_mod
            self.collector_page.number_edit.setText(collector_mod.default_number(self.collector.batch))
        app_config.save(self._collect_config())

    def _on_backend_finished(self, exit_code: int) -> None:
        self._connections = 0
        self._transfers.clear()
        self._running_since = None
        self._set_state("stopped")
        mode = self._running_mode.capitalize()
        if self._last_error:
            message, self._last_error = self._last_error, None
            QMessageBox.critical(self, f"{mode} tidak bisa berjalan", message)
        elif not self._stop_requested and exit_code != 0:
            self._append_log("error", f"Backend berhenti tiba-tiba (kode {exit_code}).")
        self._append_log("info", f"{mode} berhenti.")

    # =============================================================== helpers
    def _on_mode_toggled(self, button_id: int, checked: bool) -> None:
        if checked:
            self.mode_stack.setCurrentIndex(button_id)
            self._set_state(self._state)

    def _status_view(self) -> tuple[str, str, str, str]:
        """(color, title, subtitle, badge) for the current state."""
        mode = self._running_mode if self._state != "stopped" else self._mode()
        name = "Server" if mode == "server" else "Client"
        host = self.cfg.get("client_host", "")
        if self._state == "running":
            if mode == "client" and not self._link_up:
                return theme.ORANGE, "Menghubungkan...", f"Mencoba terhubung ke {host}", "Berjalan"
            sub = "Server aktif dan siap menerima file" if mode == "server" else f"Terhubung ke server {host}"
            return theme.GREEN, "Terhubung", sub, "Berjalan"
        if self._state == "starting":
            return theme.ORANGE, "Memulai...", f"{name} sedang dijalankan", "Memulai..."
        if self._state == "stopping":
            return theme.ORANGE, "Menghentikan...", f"{name} sedang dihentikan", "Menghentikan..."
        return "#64748b", "Tidak aktif", f"{name} belum dijalankan", "Berhenti"

    def _set_state(self, state: str) -> None:
        self._state = state
        mode_name = (self._running_mode if state != "stopped" else self._mode()).capitalize()
        self.start_btn.setText(f"Mulai {mode_name}")
        self.stop_btn.setText(f"Stop {mode_name}")
        color, title, subtitle, badge = self._status_view()
        self.conn_status.set_state(color, title, subtitle)
        self.header_status.set_state(color, title)
        self.state_badge.set_state(color, badge)
        self.start_btn.setEnabled(state == "stopped")
        self.stop_btn.setEnabled(state in ("running", "starting"))
        self._update_enabled()
        self._update_stat_cards()

    def _update_enabled(self) -> None:
        idle = self._state == "stopped"
        for widget in self._mode_widgets + self._server_widgets + self._client_widgets + self._naming_widgets:
            widget.setEnabled(idle)
        if idle:
            self.user_edit.setEnabled(not self.any_login.isChecked())
            self.pass_edit.setEnabled(not self.any_login.isChecked())
            dedup = self.dedup_check.isChecked()
            self.dedup_combo.setEnabled(dedup)
            self.keep_dup_check.setEnabled(dedup)

    def _tick(self) -> None:
        self.stats.roll_day()
        self.activity_chart.set_values(self.stats.activity())
        self._update_stat_cards()

    def _update_stat_cards(self) -> None:
        if not hasattr(self, "stat_cards"):
            return
        for key in ("received", "saved", "duplicate", "unmatched", "error"):
            self.stat_cards[key].set_data(self.stats.session[key], f"+{self.stats.today[key]} hari ini",
                                          self.stats.series(key))
        since = f"Sejak {self._running_since:%H:%M:%S}" if self._running_since and self._state == "running" else "Tidak aktif"
        self.stat_cards["connections"].set_data(self._connections, since)

    def _update_preview(self) -> None:
        line_id = naming.clean_line_id(self.line_edit.text()) or "?????"
        result = naming.build_name(self.test_edit.text(), line_id)
        if result:
            self.preview_label.setObjectName("renameResult")
            self.preview_label.setText(result)
        else:
            self.preview_label.setObjectName("renameBad")
            self.preview_label.setText("Format tidak sesuai -> masuk ke _tidak_sesuai"
                                       if self.keep_unmatched_check.isChecked()
                                       else "Format tidak sesuai -> tidak disimpan, dicatat di log txt")
        self.preview_label.style().unpolish(self.preview_label)
        self.preview_label.style().polish(self.preview_label)

    def _append_log(self, level: str, message: str, time_text: str | None = None) -> None:
        stamp = time_text or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = html.escape(f"[{stamp}] {message}")
        color = LOG_COLORS.get(level)
        self.log_view.appendHtml(f'<span style="color:{color}">{line}</span>' if color else line)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.backend.is_running():
            answer = QMessageBox.question(
                self, "Keluar", f"{self._running_mode.capitalize()} FTP masih berjalan. Hentikan dan keluar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._stop_requested = True
            self.backend.stop_blocking()
        app_config.save(self._collect_config())
        event.accept()
