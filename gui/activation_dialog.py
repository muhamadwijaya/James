"""Activation window shown at launch when the app is not yet activated."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

import activation
import hwid as hwid_mod
import icons
import theme
from widgets import IconBox


class ActivationDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Aktivasi FRT Cam")
        self.setModal(True)
        self.setMinimumWidth(560)
        self._hwid = hwid_mod.hwid()

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 18)
        root.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(14)
        head.addWidget(IconBox("camera", theme.BLUE, 46, solid=True, icon_size=25))
        titles = QVBoxLayout()
        titles.setSpacing(1)
        t = QLabel("Aktivasi FRT Cam")
        t.setStyleSheet("font-size: 14pt; font-weight: 700;")
        s = QLabel("Aplikasi perlu diaktivasi untuk komputer ini sebelum dipakai.")
        s.setObjectName("cardSubtitle")
        titles.addWidget(t)
        titles.addWidget(s)
        head.addLayout(titles)
        head.addStretch(1)
        root.addLayout(head)

        root.addWidget(self._field_label("ID Komputer (HWID)"))
        id_box = QHBoxLayout()
        id_box.setSpacing(8)
        self.id_display = QLineEdit(hwid_mod.display_id(self._hwid))
        self.id_display.setReadOnly(True)
        self.id_display.setObjectName("mono")
        self.id_display.setStyleSheet("font-family: monospace; font-weight: 700; letter-spacing: 1px;")
        copy = QPushButton("Salin")
        copy.setIcon(icons.icon("copy", theme.TEXT, 16))
        copy.setFixedWidth(96)
        copy.clicked.connect(self._copy_hwid)
        id_box.addWidget(self.id_display, 1)
        id_box.addWidget(copy)
        root.addLayout(id_box)

        note = QLabel(f"Kirim ID Komputer di atas ke <b>{activation.VENDOR_PHONE}</b> (WhatsApp/SMS) untuk "
                      "meminta <b>Kode Aktivasi</b> dan <b>OTP</b>.")
        note.setWordWrap(True)
        note.setObjectName("hint")
        root.addWidget(note)

        code_head = QHBoxLayout()
        code_head.addWidget(self._field_label("Kode Aktivasi"))
        code_head.addStretch(1)
        load = QPushButton("Muat file .lic")
        load.setIcon(icons.icon("file_text", theme.TEXT, 15))
        load.clicked.connect(self._load_lic)
        code_head.addWidget(load)
        root.addLayout(code_head)
        self.code_edit = QPlainTextEdit()
        self.code_edit.setPlaceholderText("Tempel kode aktivasi dari vendor di sini...")
        self.code_edit.setFixedHeight(70)
        self.code_edit.setObjectName("mono")
        root.addWidget(self.code_edit)

        otp_row = QHBoxLayout()
        otp_row.setSpacing(10)
        otp_row.addWidget(self._field_label("OTP (6 angka)"))
        self.otp_edit = QLineEdit()
        self.otp_edit.setMaxLength(6)
        self.otp_edit.setFixedWidth(140)
        self.otp_edit.setInputMask("999999")
        self.otp_edit.setStyleSheet("font-family: monospace; font-size: 13pt; font-weight: 700; letter-spacing: 4px;")
        otp_row.addWidget(self.otp_edit)
        otp_row.addStretch(1)
        root.addLayout(otp_row)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        root.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buy = QPushButton("Hubungi vendor")
        buy.setIcon(icons.icon("pin", theme.TEXT, 16))
        buy.clicked.connect(self._contact_vendor)
        buttons.addWidget(buy)
        buttons.addStretch(1)
        quit_btn = QPushButton("Keluar")
        quit_btn.setMinimumWidth(110)
        quit_btn.clicked.connect(self.reject)
        self.activate_btn = QPushButton("  Aktivasi")
        self.activate_btn.setObjectName("primaryButton")
        self.activate_btn.setIcon(icons.icon("check", "#ffffff", 16))
        self.activate_btn.setMinimumHeight(40)
        self.activate_btn.setMinimumWidth(150)
        self.activate_btn.clicked.connect(self._activate)
        buttons.addWidget(quit_btn)
        buttons.addWidget(self.activate_btn)
        root.addLayout(buttons)

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("formLabel")
        label.setStyleSheet("font-weight: 600;")
        return label

    def _copy_hwid(self) -> None:
        QGuiApplication.clipboard().setText(self._hwid)
        self._set_status(theme.GREEN, "ID Komputer disalin ke clipboard.")

    def _contact_vendor(self) -> None:
        digits = "".join(c for c in activation.VENDOR_PHONE if c.isdigit())
        wa = "62" + digits[1:] if digits.startswith("0") else digits
        QDesktopServices.openUrl(QUrl(f"https://wa.me/{wa}"))

    def _load_lic(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Pilih file lisensi", "", "File lisensi (*.lic *.txt);;Semua file (*)")
        if not path:
            return
        data = activation.read_lic_file(path)
        self.code_edit.setPlainText(data.get("code", ""))
        self.otp_edit.setText("".join(c for c in data.get("otp", "") if c.isdigit()))
        self._set_status(theme.MUTED, "File lisensi dimuat. Klik Aktivasi.")

    def _activate(self) -> None:
        code = self.code_edit.toPlainText().strip()
        otp = self.otp_edit.text().strip()
        if not code or len(otp) < 6:
            self._set_status(theme.ORANGE, "Isi Kode Aktivasi dan OTP (6 angka) terlebih dahulu.")
            return
        ok, message = activation.activate(code, otp)
        if ok:
            self._set_status(theme.GREEN, "Aktivasi berhasil: " + message)
            self.accept()
        else:
            self._set_status(theme.RED, message)

    def _set_status(self, color: str, text: str) -> None:
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {color}; font-weight: 600;")


def ensure_activated() -> bool:
    """True if already activated, or the user activates now. False if they choose to quit."""
    if activation.is_activated():
        return True
    dialog = ActivationDialog()
    return dialog.exec() == QDialog.DialogCode.Accepted

