"""'Foto terakhir disimpan' panel: big photo, zoom, fullscreen, history thumbnails and details."""
from __future__ import annotations

import html
import os
import re
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QImageReader, QPixmap
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

import icons
import theme
from widgets import Card, FullscreenViewer, ImageView, human_size

# 00001_20261014_121653_BXXAXESPP.jpg -> photo time 2026-10-14 12:16:53
_SAVED_NAME = re.compile(r"_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})_[^_]+(?:_\d+)?\.\w+$")
MAX_DECODE_PX = 2048      # enough detail for zooming, still light in memory
LOAD_INTERVAL_MS = 250    # continuous traffic: at most ~4 decodes per second (newest only)
HISTORY = 12              # photos kept in the thumbnail strip
VISIBLE_THUMBS = 5


def _read_image(path: str, max_px: int):
    reader = QImageReader(path)
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and max(size.width(), size.height()) > max_px:
        reader.setScaledSize(size.scaled(max_px, max_px, Qt.AspectRatioMode.KeepAspectRatio))
    image = reader.read()
    del reader  # release the file handle right away
    return image, size


class _RoundButton(QPushButton):
    def __init__(self, icon_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setIcon(icons.icon(icon_name, "#ffffff", 18, 2.4))
        self.setIconSize(QSize(18, 18))
        self.setFixedSize(34, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QPushButton { background: rgba(10, 20, 40, 170); border: 1px solid rgba(255,255,255,60);"
                           " border-radius: 17px; padding: 0; } QPushButton:hover { background: rgba(47,128,255,200); }")


class _Thumb(QPushButton):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(62, 46)
        self.setIconSize(QSize(56, 40))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            "QPushButton { background: #060d1a; border: 1px solid #1f3355; border-radius: 6px; padding: 2px; }"
            f"QPushButton:checked {{ border: 2px solid {theme.BLUE}; }}"
            "QPushButton:hover { border-color: #3b6fc4; }")


class PhotoPanel(Card):
    def __init__(self, parent=None) -> None:
        super().__init__(parent=parent, margins=(16, 12, 16, 14))
        header = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(icons.pixmap("image", theme.BLUE, 22))
        title = QLabel("Foto terakhir disimpan")
        title.setObjectName("cardTitle")
        header.addWidget(title_icon)
        header.addSpacing(6)
        header.addWidget(title)
        header.addStretch(1)
        self.zoom_in_btn = self._tool_button("zoom_in", "Perbesar", lambda: self.view.zoom_by(1.25))
        self.zoom_out_btn = self._tool_button("zoom_out", "Perkecil", lambda: self.view.zoom_by(1 / 1.25))
        self.full_btn = self._tool_button("fullscreen", "Layar penuh", self._fullscreen)
        for b in (self.zoom_in_btn, self.zoom_out_btn, self.full_btn):
            header.addWidget(b)
        self.body.addLayout(header)

        self.view = ImageView()
        self.view.setToolTip("Scroll untuk zoom, geser untuk pindah, klik dua kali untuk membuka foto")
        self.view.doubleClicked.connect(self._open_current)
        self.prev_btn = _RoundButton("chevron_left", self.view)
        self.next_btn = _RoundButton("chevron_right", self.view)
        self.prev_btn.setToolTip("Foto lebih baru")
        self.next_btn.setToolTip("Foto sebelumnya")
        self.prev_btn.clicked.connect(lambda: self._select(self._index - 1))
        self.next_btn.clicked.connect(lambda: self._select(self._index + 1))
        self.view.installEventFilter(self)
        self.body.addWidget(self.view, 1)

        strip = QHBoxLayout()
        strip.setSpacing(7)
        self._thumbs: list[_Thumb] = []
        for i in range(VISIBLE_THUMBS):
            t = _Thumb()
            t.clicked.connect(lambda _=False, i=i: self._select(self._offset + i))
            self._thumbs.append(t)
            strip.addWidget(t)
        self.more_btn = QPushButton()
        self.more_btn.setObjectName("iconButton")
        self.more_btn.setIcon(icons.icon("chevron_right", theme.MUTED, 16))
        self.more_btn.setFixedSize(22, 46)
        self.more_btn.setToolTip("Foto lainnya")
        self.more_btn.clicked.connect(self._page_thumbs)
        strip.addWidget(self.more_btn)
        strip.addStretch(1)
        self.body.addLayout(strip)

        self.name_label = QLabel("-")
        self.name_label.setStyleSheet("font-size: 10pt; font-weight: 700;")
        self.name_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body.addWidget(self.name_label)

        info = QGridLayout()
        info.setHorizontalSpacing(18)
        info.setVerticalSpacing(6)
        self._info: dict[str, QLabel] = {}
        for i, (key, icon_name, title_text) in enumerate((
            ("code", "tag", "Code"), ("photo_time", "clock", "Waktu foto"),
            ("client", "pin", "Dari"), ("received", "file_text", "Diterima"),
            ("size", "gauge", "Ukuran"), ("resolution", "grid", "Resolusi"),
        )):
            cell = QWidget()
            row = QHBoxLayout(cell)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            ic = QLabel()
            ic.setPixmap(icons.pixmap(icon_name, theme.MUTED, 16))
            label = QLabel(f"{title_text}: -")
            label.setStyleSheet("font-size: 8.5pt;")
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            label.setMinimumWidth(60)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setProperty("title", title_text)
            row.addWidget(ic)
            row.addWidget(label, 1)
            self._info[key] = label
            info.addWidget(cell, i // 2, i % 2)
        info.setColumnStretch(0, 42)
        info.setColumnStretch(1, 58)
        self.body.addLayout(info)

        self._history: list[dict] = []   # newest first: {"event", "path", "thumb"}
        self._index = -1
        self._offset = 0
        self._pending: dict | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(LOAD_INTERVAL_MS)
        self._timer.timeout.connect(self._flush_pending)
        self._update_controls()

    # ------------------------------------------------------------------ API
    @property
    def current_path(self) -> str | None:
        if 0 <= self._index < len(self._history):
            return self._history[self._index]["path"]
        return None

    def show_saved(self, event: dict) -> None:
        """New saved photo from the backend; decoding is throttled to the newest one."""
        self._pending = event
        if not self._timer.isActive():
            self._timer.start()

    def show_event_now(self, event: dict) -> None:
        """Show a photo picked by the user (eye button), adding it to the history if needed."""
        path = event.get("path") or ""
        for i, entry in enumerate(self._history):
            if entry["path"] == path:
                self._select(i)
                return
        self._add(event)

    # ------------------------------------------------------------ internals
    def _tool_button(self, icon_name: str, tip: str, slot) -> QPushButton:
        b = QPushButton()
        b.setObjectName("iconButton")
        b.setIcon(icons.icon(icon_name, theme.TEXT, 18))
        b.setIconSize(QSize(18, 18))
        b.setFixedSize(36, 32)
        b.setToolTip(tip)
        b.clicked.connect(slot)
        return b

    def _flush_pending(self) -> None:
        event, self._pending = self._pending, None
        if event:
            self._add(event)

    def _add(self, event: dict) -> None:
        path = event.get("path") or ""
        self._history = [e for e in self._history if e["path"] != path]
        self._history.insert(0, {"event": event, "path": path, "thumb": None})
        del self._history[HISTORY:]
        self._offset = 0
        self._select(0)

    def _select(self, index: int) -> None:
        if not self._history:
            return
        index = max(0, min(len(self._history) - 1, index))
        self._index = index
        if index < self._offset:
            self._offset = index
        elif index >= self._offset + VISIBLE_THUMBS:
            self._offset = index - VISIBLE_THUMBS + 1
        entry = self._history[index]
        event, path = entry["event"], entry["path"]
        name = event.get("name") or Path(path).name

        image, original = _read_image(path, MAX_DECODE_PX)
        if image.isNull():
            self.view.set_pixmap(None, f"Foto tidak bisa ditampilkan\n{name}")
        else:
            self.view.set_pixmap(QPixmap.fromImage(image))

        m = _SAVED_NAME.search(name)
        photo_time = f"{m[1]}-{m[2]}-{m[3]} {m[4]}:{m[5]}:{m[6]}" if m else "-"
        try:
            size = human_size(os.path.getsize(path))
        except OSError:
            size = "-"
        resolution = f"{original.width()} x {original.height()}" if original.isValid() else "-"
        self.name_label.setText(html.escape(name))
        self.name_label.setToolTip(path)
        self._set_info("code", event.get("code") or "-")
        self._set_info("photo_time", photo_time)
        self._set_info("client", event.get("client") or "-")
        self._set_info("received", event.get("time") or "-")
        self._set_info("size", size)
        self._set_info("resolution", resolution)
        self._update_controls()

    def _set_info(self, key: str, value: str) -> None:
        label = self._info[key]
        label.setText(f"{label.property('title')}: {value}")

    def _thumb_icon(self, entry: dict):
        if entry["thumb"] is None:
            image, _ = _read_image(entry["path"], 160)
            entry["thumb"] = QPixmap.fromImage(image) if not image.isNull() else QPixmap()
        return entry["thumb"]

    def _update_controls(self) -> None:
        count = len(self._history)
        for i, thumb in enumerate(self._thumbs):
            idx = self._offset + i
            if idx < count:
                entry = self._history[idx]
                thumb.setIcon(self._thumb_icon(entry))
                thumb.setToolTip(entry["event"].get("name") or entry["path"])
                thumb.setChecked(idx == self._index)
                thumb.setEnabled(True)
                thumb.setVisible(True)
            else:
                thumb.setIcon(QPixmap())
                thumb.setChecked(False)
                thumb.setEnabled(False)
                thumb.setToolTip("")
        self.more_btn.setEnabled(count > VISIBLE_THUMBS)
        self.prev_btn.setVisible(self._index > 0)
        self.next_btn.setVisible(0 <= self._index < count - 1)
        has = self.current_path is not None and self.view.pixmap() is not None
        for b in (self.zoom_in_btn, self.zoom_out_btn, self.full_btn):
            b.setEnabled(has)

    def _page_thumbs(self) -> None:
        count = len(self._history)
        self._offset = 0 if self._offset + VISIBLE_THUMBS >= count else self._offset + VISIBLE_THUMBS
        self._update_controls()

    def _fullscreen(self) -> None:
        pm = self.view.pixmap()
        if pm is None:
            return
        viewer = FullscreenViewer(pm, Path(self.current_path or "").name, self)
        viewer.showFullScreen()
        viewer.exec()

    def _open_current(self) -> None:
        path = self.current_path
        if path and Path(path).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.view and event.type() == event.Type.Resize:
            y = (self.view.height() - self.prev_btn.height()) // 2
            self.prev_btn.move(12, y)
            self.next_btn.move(self.view.width() - self.next_btn.width() - 12, y)
        return super().eventFilter(obj, event)

