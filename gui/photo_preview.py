"""Panel that shows the most recently saved photo."""
from __future__ import annotations

import html
import re
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QImageReader, QPixmap
from PySide6.QtWidgets import QGroupBox, QLabel, QSizePolicy, QVBoxLayout

# 00001_20261014_121653_BXXAXESPP.jpg -> photo time 2026-10-14 12:16:53
_SAVED_NAME = re.compile(r"_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_[^_]+(?:_\d+)?\.\w+$")
MAX_DECODE_PX = 1280     # longest edge kept in memory; camera photos are decoded smaller
LOAD_INTERVAL_MS = 250   # with continuous traffic: at most ~4 decodes per second, newest photo only


class _ImageLabel(QLabel):
    def __init__(self) -> None:
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(260, 200)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setStyleSheet("background:#111827; color:#9ca3af; border-radius:4px;")
        self.setText("Belum ada foto tersimpan")
        self._pixmap: QPixmap | None = None
        self.path: str | None = None

    def show_pixmap(self, pixmap: QPixmap | None, path: str | None, message: str = "") -> None:
        self._pixmap = pixmap
        self.path = path
        self.setToolTip(f"{path}\nKlik dua kali untuk membuka" if path else "")
        if pixmap is None:
            self.setPixmap(QPixmap())
            self.setText(message)
        else:
            self._fit()

    def _fit(self) -> None:
        if self._pixmap is not None:
            self.setPixmap(self._pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        super().resizeEvent(event)
        self._fit()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self.path and Path(self.path).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.path))


class PhotoPreview(QGroupBox):
    def __init__(self, parent=None) -> None:
        super().__init__("Foto terakhir disimpan", parent)
        layout = QVBoxLayout(self)
        self.image = _ImageLabel()
        self.caption = QLabel("-")
        self.caption.setWordWrap(True)
        self.caption.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.image, 1)
        layout.addWidget(self.caption)

        self._pending: dict | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(LOAD_INTERVAL_MS)
        self._timer.timeout.connect(self._load_pending)

    def show_saved(self, event: dict) -> None:
        """Queue a 'saved' file event from the backend; only the newest one gets decoded."""
        self._pending = event
        if not self._timer.isActive():
            self._timer.start()

    def _load_pending(self) -> None:
        event, self._pending = self._pending, None
        if not event:
            return
        path = event.get("path") or ""
        name = event.get("name") or Path(path).name

        reader = QImageReader(path)
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid() and max(size.width(), size.height()) > MAX_DECODE_PX:
            reader.setScaledSize(size.scaled(MAX_DECODE_PX, MAX_DECODE_PX, Qt.AspectRatioMode.KeepAspectRatio))
        image = reader.read()
        del reader  # release the file handle right away
        if image.isNull():
            self.image.show_pixmap(None, path, f"Foto tidak bisa ditampilkan\n{name}")
        else:
            self.image.show_pixmap(QPixmap.fromImage(image), path)

        m = _SAVED_NAME.search(name)
        photo_time = f"{m[1]}-{m[2]}-{m[3]} {m[4]}:{m[5]}:{m[6]}" if m else "-"
        esc = html.escape
        self.caption.setText(
            f"<b>{esc(name)}</b><br>"
            f"Code: <b>{esc(event.get('code') or '-')}</b> &nbsp;&middot;&nbsp; Waktu foto: {esc(photo_time)}<br>"
            f"Dari: {esc(event.get('client') or '-')} &nbsp;&middot;&nbsp; Diterima: {esc(event.get('time') or '-')}"
        )
