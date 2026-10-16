"""FRT Cam - Pembuat Lisensi (vendor tool, GUI).

A standalone app for the vendor (you) to issue activation codes for customer PCs.
It never ships to customers. The vendor private key lives in a `vendor_keys` folder
next to this program (created by "Buat kunci vendor"); only the public key goes into
the main app (gui/activation.py) which you then rebuild.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

import activation
import ed25519
import hwid as hwid_mod
import icons
import theme
from widgets import Card, IconBox

try:
    import secrets as _secrets

    def _random_otp() -> str:
        return f"{_secrets.randbelow(1_000_000):06d}"

    def _random_seed() -> bytes:
        return _secrets.token_bytes(32)
except Exception:  # pragma: no cover
    import os

    def _random_otp() -> str:
        return f"{int.from_bytes(os.urandom(3), 'big') % 1_000_000:06d}"

    def _random_seed() -> bytes:
        return os.urandom(32)

APP_TITLE = "FRT Cam - Pembuat Lisensi"
APP_VERSION = "2.0.0"
DURATIONS = [("Selamanya", 0), ("30 hari", 30), ("90 hari", 90), ("180 hari", 180),
             ("365 hari (1 tahun)", 365), ("Pilih sendiri...", -1)]


def key_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "vendor_keys"
    return Path(__file__).resolve().parent.parent / "tools" / "vendor_keys"


def private_file() -> Path:
    return key_dir() / "private_seed.hex"


def load_seed() -> tuple[bytes, bool]:
    """(seed, is_demo)."""
    path = private_file()
    if path.exists():
        try:
            return bytes.fromhex(path.read_text(encoding="ascii").strip()), False
        except (OSError, ValueError):
            pass
    import hashlib
    phrase = b"FRT Cam DEMO vendor key v2 - regenerate with: python tools/license_tool.py keygen"
    return hashlib.sha256(phrase).digest(), True


class VendorWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(760, 860)
        self.setStyleSheet(f"QWidget {{ background: {theme.BG}; }}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(20, 18, 20, 20)
        root.setSpacing(14)

        root.addLayout(self._header())
        root.addWidget(self._key_card())
        root.addWidget(self._issue_card())
        root.addWidget(self._result_card())
        root.addStretch(1)
        self._refresh_key_status()

    # ------------------------------------------------------------------ header
    def _header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(14)
        row.addWidget(IconBox("key", theme.BLUE, 46, solid=True, icon_size=24))
        texts = QVBoxLayout()
        texts.setSpacing(1)
        t = QLabel("Pembuat Lisensi FRT Cam")
        t.setStyleSheet("font-size: 15pt; font-weight: 700;")
        s = QLabel("Buat kode aktivasi + OTP untuk komputer pelanggan. Hanya untuk vendor.")
        s.setObjectName("cardSubtitle")
        texts.addWidget(t)
        texts.addWidget(s)
        row.addLayout(texts)
        row.addStretch(1)
        ver = QLabel(f"v{APP_VERSION}")
        ver.setObjectName("muted")
        row.addWidget(ver, 0, Qt.AlignmentFlag.AlignTop)
        return row

    # ------------------------------------------------------------- key card
    def _key_card(self) -> Card:
        card = Card("Kunci Vendor", "Kunci privat untuk menandatangani kode aktivasi", "shield")
        self.key_status = QLabel()
        self.key_status.setWordWrap(True)
        card.body.addWidget(self.key_status)

        pub_row = QHBoxLayout()
        pub_row.setSpacing(8)
        label = QLabel("Kunci publik")
        label.setObjectName("formLabel")
        self.pub_edit = QLineEdit()
        self.pub_edit.setReadOnly(True)
        self.pub_edit.setObjectName("mono")
        self.pub_edit.setStyleSheet("font-family: monospace;")
        copy_pub = QPushButton("Salin")
        copy_pub.setIcon(icons.icon("copy", theme.TEXT, 15))
        copy_pub.setFixedWidth(90)
        copy_pub.clicked.connect(lambda: self._copy(self.pub_edit.text(), "Kunci publik disalin."))
        pub_row.addWidget(label)
        pub_row.addWidget(self.pub_edit, 1)
        pub_row.addWidget(copy_pub)
        card.body.addLayout(pub_row)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.keygen_btn = QPushButton("  Buat kunci vendor sendiri")
        self.keygen_btn.setIcon(icons.icon("key", theme.TEXT, 16))
        self.keygen_btn.clicked.connect(self._keygen)
        save_pub = QPushButton("  Simpan kunci publik (.txt)")
        save_pub.setIcon(icons.icon("file_text", theme.TEXT, 16))
        save_pub.clicked.connect(self._save_pub)
        buttons.addWidget(self.keygen_btn)
        buttons.addWidget(save_pub)
        buttons.addStretch(1)
        card.body.addLayout(buttons)
        return card

    # ------------------------------------------------------------- issue card
    def _issue_card(self) -> Card:
        card = Card("Buat Kode Aktivasi", "Isi HWID dari pelanggan, lalu klik Buat Kode", "file_check")
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(9)
        grid.setColumnStretch(1, 1)

        self.hwid_edit = QLineEdit()
        self.hwid_edit.setPlaceholderText("Tempel HWID 64 karakter dari jendela Aktivasi pelanggan")
        self.hwid_edit.setObjectName("mono")
        self.hwid_edit.setStyleSheet("font-family: monospace;")
        use_mine = QPushButton("HWID PC ini")
        use_mine.setFixedWidth(130)
        use_mine.setToolTip("Isi dengan HWID komputer ini (untuk uji coba)")
        use_mine.clicked.connect(lambda: self.hwid_edit.setText(hwid_mod.hwid()))

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("opsional, mis. PT Contoh / Toko A")

        self.dur_combo = QComboBox()
        for text, days in DURATIONS:
            self.dur_combo.addItem(text, days)
        self.dur_combo.currentIndexChanged.connect(self._dur_changed)
        self.custom_days = QSpinBox()
        self.custom_days.setRange(1, 36500)
        self.custom_days.setValue(30)
        self.custom_days.setSuffix(" hari")
        self.custom_days.setVisible(False)

        self.otp_edit = QLineEdit()
        self.otp_edit.setInputMask("999999")
        self.otp_edit.setText(_random_otp())
        self.otp_edit.setFixedWidth(130)
        self.otp_edit.setStyleSheet("font-family: monospace; font-size: 12pt; letter-spacing: 3px;")
        otp_random = QPushButton("Acak")
        otp_random.setFixedWidth(80)
        otp_random.clicked.connect(lambda: self.otp_edit.setText(_random_otp()))

        def lab(text: str) -> QLabel:
            label = QLabel(text)
            label.setObjectName("formLabel")
            return label

        grid.addWidget(lab("HWID"), 0, 0)
        hwid_row = QHBoxLayout()
        hwid_row.setSpacing(8)
        hwid_row.addWidget(self.hwid_edit, 1)
        hwid_row.addWidget(use_mine)
        grid.addLayout(hwid_row, 0, 1)
        grid.addWidget(lab("Nama pelanggan"), 1, 0)
        grid.addWidget(self.name_edit, 1, 1)
        grid.addWidget(lab("Masa berlaku"), 2, 0)
        dur_row = QHBoxLayout()
        dur_row.setSpacing(10)
        dur_row.addWidget(self.dur_combo)
        dur_row.addWidget(self.custom_days)
        dur_row.addStretch(1)
        grid.addLayout(dur_row, 2, 1)
        grid.addWidget(lab("OTP (6 angka)"), 3, 0)
        otp_row = QHBoxLayout()
        otp_row.setSpacing(10)
        otp_row.addWidget(self.otp_edit)
        otp_row.addWidget(otp_random)
        otp_row.addStretch(1)
        grid.addLayout(otp_row, 3, 1)
        card.body.addLayout(grid)

        make = QPushButton("  Buat Kode")
        make.setObjectName("primaryButton")
        make.setIcon(icons.icon("check", "#ffffff", 16))
        make.setMinimumHeight(42)
        make.clicked.connect(self._issue)
        card.body.addWidget(make)
        return card

    # ------------------------------------------------------------- result card
    def _result_card(self) -> Card:
        card = Card("Hasil", "Kirim KODE dan OTP ini ke pelanggan", "key")
        self.result_code = QPlainTextEdit()
        self.result_code.setReadOnly(True)
        self.result_code.setFixedHeight(80)
        self.result_code.setObjectName("mono")
        self.result_code.setPlaceholderText("Kode aktivasi akan muncul di sini...")
        card.body.addWidget(self.result_code)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.result_otp = QLabel("OTP: -")
        self.result_otp.setStyleSheet(f"color: {theme.CYAN}; font-family: monospace; font-size: 13pt; font-weight: 700;")
        self.result_meta = QLabel("")
        self.result_meta.setObjectName("muted")
        row.addWidget(self.result_otp)
        row.addSpacing(16)
        row.addWidget(self.result_meta)
        row.addStretch(1)
        card.body.addLayout(row)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.copy_code = QPushButton("  Salin Kode")
        self.copy_code.setIcon(icons.icon("copy", theme.TEXT, 16))
        self.copy_code.clicked.connect(lambda: self._copy(self.result_code.toPlainText(), "Kode aktivasi disalin."))
        self.copy_otp = QPushButton("  Salin OTP")
        self.copy_otp.setIcon(icons.icon("copy", theme.TEXT, 16))
        self.copy_otp.clicked.connect(lambda: self._copy(self._last_otp, "OTP disalin."))
        self.copy_all = QPushButton("  Salin Kode + OTP")
        self.copy_all.setIcon(icons.icon("copy", theme.TEXT, 16))
        self.copy_all.clicked.connect(self._copy_all)
        self.save_lic = QPushButton("  Simpan file .lic")
        self.save_lic.setIcon(icons.icon("file_text", theme.TEXT, 16))
        self.save_lic.clicked.connect(self._save_lic)
        for b in (self.copy_code, self.copy_otp, self.copy_all, self.save_lic):
            b.setEnabled(False)
            buttons.addWidget(b)
        buttons.addStretch(1)
        card.body.addLayout(buttons)
        self._last = None
        self._last_otp = ""
        return card

    # ------------------------------------------------------------------ logic
    def _dur_changed(self) -> None:
        self.custom_days.setVisible(self.dur_combo.currentData() == -1)

    def _selected_days(self) -> int:
        data = self.dur_combo.currentData()
        return self.custom_days.value() if data == -1 else data

    def _refresh_key_status(self) -> None:
        seed, demo = load_seed()
        pub = ed25519.publickey(seed).hex()
        self.pub_edit.setText(pub)
        matches = pub == activation.VENDOR_PUBLIC_KEY_HEX
        if demo:
            self.key_status.setText(
                "⚠  Memakai <b>kunci DEMO</b> bawaan (kuncinya diketahui umum). "
                "Untuk produksi, klik <b>Buat kunci vendor sendiri</b> lalu build ulang aplikasi utama.")
            self.key_status.setStyleSheet(f"color: {theme.ORANGE};")
        elif matches:
            self.key_status.setText("✔  Memakai kunci vendor Anda sendiri. Aplikasi utama sudah cocok dengan kunci ini.")
            self.key_status.setStyleSheet(f"color: {theme.GREEN};")
        else:
            self.key_status.setText(
                "⚠  Kunci vendor Anda sudah ada, tapi aplikasi utama <b>belum di-build</b> dengan kunci ini. "
                "Tempel kunci publik di bawah ke gui/activation.py (VENDOR_PUBLIC_KEY_HEX) lalu jalankan build.bat.")
            self.key_status.setStyleSheet(f"color: {theme.ORANGE};")

    def _keygen(self) -> None:
        if private_file().exists():
            answer = QMessageBox.warning(
                self, "Buat kunci baru",
                "Kunci vendor sudah ada. Membuat kunci baru akan membuat SEMUA kode aktivasi lama "
                "tidak berlaku, dan aplikasi utama harus di-build ulang.\n\nLanjutkan?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        try:
            key_dir().mkdir(parents=True, exist_ok=True)
            seed = _random_seed()
            private_file().write_text(seed.hex(), encoding="ascii")
        except OSError as exc:
            QMessageBox.critical(self, "Buat kunci", f"Gagal menyimpan kunci:\n{exc}")
            return
        pub = ed25519.publickey(seed).hex()
        self._refresh_key_status()
        QMessageBox.information(
            self, "Kunci vendor dibuat",
            f"Kunci privat disimpan di:\n{private_file()}\n(JANGAN dibagikan / jangan di-commit)\n\n"
            f"Kunci publik:\n{pub}\n\nLangkah berikutnya:\n"
            "1. Tempel kunci publik di atas ke gui/activation.py  (VENDOR_PUBLIC_KEY_HEX).\n"
            "2. Jalankan build.bat untuk membuat ulang aplikasi utama.")

    def _save_pub(self) -> None:
        dest, _ = QFileDialog.getSaveFileName(self, "Simpan kunci publik", "kunci_publik.txt", "Teks (*.txt)")
        if dest:
            try:
                Path(dest).write_text(
                    f'VENDOR_PUBLIC_KEY_HEX = "{self.pub_edit.text()}"\n', encoding="utf-8")
            except OSError as exc:
                QMessageBox.critical(self, "Simpan", f"Gagal menyimpan:\n{exc}")

    def _issue(self) -> None:
        hv = "".join(self.hwid_edit.text().split()).lower()
        if len(hv) != 64 or any(c not in "0123456789abcdef" for c in hv):
            QMessageBox.warning(self, "HWID", "HWID harus 64 karakter hex. Salin lengkap dari jendela Aktivasi pelanggan.")
            return
        otp = self.otp_edit.text()
        if len(otp) != 6 or not otp.isdigit():
            QMessageBox.warning(self, "OTP", "OTP harus 6 angka.")
            return
        seed, demo = load_seed()
        pub = ed25519.publickey(seed).hex()
        days = self._selected_days()
        expiry = 0 if days <= 0 else activation.days_from_date(date.today() + timedelta(days=days))
        name = self.name_edit.text().strip()
        code = activation.sign_payload(seed, hv, name, expiry, otp)

        self.result_code.setPlainText(code)
        self.result_otp.setText(f"OTP: {otp}")
        masa = "selamanya" if expiry == 0 else f"s/d {date.today() + timedelta(days=days):%Y-%m-%d}"
        self.result_meta.setText(f"{name or '-'}  ·  {masa}")
        self._last = {"hwid": hv, "code": code, "otp": otp, "name": name}
        self._last_otp = otp
        for b in (self.copy_code, self.copy_otp, self.copy_all, self.save_lic):
            b.setEnabled(True)
        if pub != activation.VENDOR_PUBLIC_KEY_HEX:
            note = ("kunci DEMO" if demo else "kunci yang belum di-build ke aplikasi")
            QMessageBox.warning(self, "Perhatian",
                                f"Kode dibuat dengan {note}. Kode ini hanya diterima aplikasi yang "
                                "di-build dengan kunci publik yang cocok.")

    def _copy_all(self) -> None:
        if self._last:
            self._copy(f"Kode Aktivasi:\n{self._last['code']}\n\nOTP: {self._last['otp']}", "Kode + OTP disalin.")

    def _save_lic(self) -> None:
        if not self._last:
            return
        default = f"lisensi_{self._last['name'] or self._last['hwid'][:8]}.lic".replace(" ", "_")
        dest, _ = QFileDialog.getSaveFileName(self, "Simpan file lisensi", default, "File lisensi (*.lic)")
        if dest:
            try:
                activation.write_lic_file(dest, self._last["hwid"], self._last["code"],
                                          self._last["otp"], self._last["name"])
                QMessageBox.information(self, "Simpan", f"File lisensi disimpan:\n{dest}")
            except OSError as exc:
                QMessageBox.critical(self, "Simpan", f"Gagal menyimpan:\n{exc}")

    def _copy(self, text: str, message: str) -> None:
        if text:
            QGuiApplication.clipboard().setText(text)


def main() -> int:
    sys.setrecursionlimit(5000)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setStyle("Fusion")
    font = QFont()
    font.setFamilies(theme.FONT_FAMILIES)
    font.setPointSizeF(9)
    app.setFont(font)
    app.setStyleSheet(theme.stylesheet())
    from main import app_icon
    app.setWindowIcon(app_icon())
    window = VendorWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

