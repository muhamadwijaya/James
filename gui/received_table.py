"""Table of received files (newest 50): model, filter, delegates and the card around it."""
from __future__ import annotations

from collections import deque

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QObject, QRectF, QSize, QSortFilterProxyModel, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QTableView,
)

import icons
import theme
from widgets import Card, ToggleSwitch, dot_pixmap, qcolor

COLUMNS = ["Waktu", "Dari", "Nama asli (FTP)", "Nama baru", "Code", "Status", "Aksi"]
COL_TIME, COL_FROM, COL_ORIGINAL, COL_NAME, COL_CODE, COL_STATUS, COL_ACTION = range(7)
ROW_ROLE = Qt.ItemDataRole.UserRole + 1
STATUS_FILTERS = [("Semua status", None), ("Disimpan", "saved"), ("Duplikat", "duplicate"),
                  ("Tidak sesuai", "unmatched"), ("Gagal", "error")]
REFRESH_MS = 3000


def status_text(row: dict) -> str:
    if row["status"] == "duplicate":
        return theme.STATUS_TEXT["duplicate_kept" if row.get("path") else "duplicate"]
    return theme.STATUS_TEXT.get(row["status"], row["status"])


class ReceivedModel(QAbstractTableModel):
    """Keeps the newest rows in a buffer; the view is refreshed in batches (auto-refresh)."""

    def __init__(self, max_rows: int = 50, parent=None) -> None:
        super().__init__(parent)
        self._buffer: deque[dict] = deque(maxlen=max_rows)
        self._rows: list[dict] = []
        self._seq = 0
        self._dirty = False
        self._dot = dot_pixmap(theme.BLUE, 8)

    def add(self, event: dict) -> None:
        self._seq += 1
        self._buffer.appendleft({
            "seq": self._seq,
            "time": event.get("time") or "",
            "client": event.get("client") or "",
            "original": event.get("original") or "",
            "name": event.get("name") or "",
            "code": event.get("code") or "",
            "status": event.get("status") or "error",
            "message": event.get("message") or "",
            "path": event.get("path") or "",
        })
        self._dirty = True

    def refresh(self) -> None:
        if not self._dirty:
            return
        self.beginResetModel()
        self._rows = list(self._buffer)
        self._dirty = False
        self.endResetModel()

    def clear(self) -> None:
        self.beginResetModel()
        self._buffer.clear()
        self._rows = []
        self._dirty = False
        self.endResetModel()

    def row(self, i: int) -> dict:
        return self._rows[i]

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        if role == Qt.ItemDataRole.TextAlignmentRole and section == COL_ACTION:
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        col = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            if col == COL_TIME:
                return row["time"][-8:]
            if col == COL_FROM:
                return row["client"]
            if col == COL_ORIGINAL:
                return row["original"]
            if col == COL_NAME:
                return row["name"] or "-"
            if col == COL_CODE:
                return row["code"] or "-"
            if col == COL_STATUS:
                return status_text(row)
            return None
        if role == Qt.ItemDataRole.DecorationRole and col == COL_TIME:
            return self._dot
        if role == Qt.ItemDataRole.ToolTipRole:
            if col == COL_ORIGINAL:
                return row["original"]
            if col == COL_NAME:
                return row["path"] or row["name"]
            if col == COL_STATUS:
                return row["message"] or status_text(row)
            if col == COL_ACTION:
                return "Lihat foto" if row["path"] else "Lihat detail"
            return None
        if role == Qt.ItemDataRole.UserRole:  # sort key
            if col == COL_TIME:
                return row["seq"]
            if col == COL_STATUS:
                return row["status"]
            return self.data(index, Qt.ItemDataRole.DisplayRole)
        if role == ROW_ROLE:
            return row
        if role == Qt.ItemDataRole.ForegroundRole and col in (COL_FROM, COL_CODE):
            return QColor("#d7e1f0")
        return None


class ReceivedFilter(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._search = ""
        self._status: str | None = None
        self.setSortRole(Qt.ItemDataRole.UserRole)

    def set_search(self, text: str) -> None:
        self._search = text.strip().lower()
        self.invalidateFilter()

    def set_status(self, status: str | None) -> None:
        self._status = status
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # noqa: N802
        row = self.sourceModel().row(source_row)
        if self._status and row["status"] != self._status:
            return False
        if self._search:
            hay = f'{row["original"]} {row["name"]} {row["code"]} {row["client"]}'.lower()
            return self._search in hay
        return True


class TableController(QObject):
    """Shared filter/auto-refresh state for every table card showing the same data."""

    changed = Signal()

    def __init__(self, model: ReceivedModel, proxy: ReceivedFilter, parent=None) -> None:
        super().__init__(parent)
        self.model = model
        self.proxy = proxy
        self.search = ""
        self.status_index = 0
        self.auto_refresh = True
        self._timer = QTimer(self)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self.refresh)
        self._timer.start()

    def refresh(self) -> None:
        if self.auto_refresh:
            self.model.refresh()

    def set_search(self, text: str) -> None:
        self.search = text
        self.proxy.set_search(text)
        self.changed.emit()

    def set_status_index(self, index: int) -> None:
        self.status_index = index
        self.proxy.set_status(STATUS_FILTERS[index][1])
        self.changed.emit()

    def set_auto_refresh(self, on: bool) -> None:
        self.auto_refresh = on
        if on:
            self.model.refresh()
        self.changed.emit()

    def clear(self) -> None:
        self.model.clear()


class StatusDelegate(QStyledItemDelegate):
    """Status as a colored pill."""

    def paint(self, painter: QPainter, option, index) -> None:
        row = index.data(ROW_ROLE)
        if row is None:
            return super().paint(painter, option, index)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, qcolor(theme.BLUE, 0.16))
        text = status_text(row)
        color = theme.STATUS_COLORS.get(row["status"], theme.RED)
        fm = QFontMetrics(option.font)
        w = min(option.rect.width() - 8, fm.horizontalAdvance(text) + 18)
        h = min(option.rect.height() - 8, fm.height() + 6)
        r = QRectF(option.rect.left() + 4, option.rect.center().y() - h / 2 + 0.5, w, h)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(qcolor(color, 0.85), 1))
        painter.setBrush(qcolor(color, 0.12))
        painter.drawRoundedRect(r, 5, 5)
        painter.setPen(QColor(color))
        painter.setFont(option.font)
        painter.drawText(r, Qt.AlignmentFlag.AlignCenter, fm.elidedText(text, Qt.TextElideMode.ElideRight, int(w - 8)))
        painter.restore()


class ActionDelegate(QStyledItemDelegate):
    """Eye icon button in the 'Aksi' column."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._eye = icons.pixmap("eye", theme.TEXT, 16)
        self._eye_dim = icons.pixmap("eye", theme.MUTED, 16)

    def paint(self, painter: QPainter, option, index) -> None:
        row = index.data(ROW_ROLE)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, qcolor(theme.BLUE, 0.16))
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        box = QRectF(option.rect.center().x() - 15, option.rect.center().y() - 11, 30, 22)
        painter.setPen(QPen(qcolor("#2a4370"), 1))
        painter.setBrush(qcolor("#11223f"))
        painter.drawRoundedRect(box, 6, 6)
        pm = self._eye if row and row.get("path") else self._eye_dim
        painter.drawPixmap(int(box.center().x() - 8), int(box.center().y() - 8), pm)
        painter.restore()

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(44, 30)


class FileTableCard(Card):
    """'File Diterima (50 terbaru)' card: search, status filter, clear, auto-refresh and the table."""

    rowActivated = Signal(dict)

    def __init__(self, controller: TableController, title: str, extra_buttons=(), parent=None) -> None:
        super().__init__(parent=parent, margins=(16, 12, 16, 10))
        self.controller = controller
        header = QHBoxLayout()
        header.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(icons.pixmap("file_text", theme.BLUE, 22))
        self.title = QLabel(title)
        self.title.setObjectName("cardTitle")
        header.addWidget(icon)
        header.addWidget(self.title)
        header.addStretch(1)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Cari nama file...")
        self.search.addAction(icons.icon("search", theme.MUTED, 16), QLineEdit.ActionPosition.LeadingPosition)
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(116)
        self.search.setMaximumWidth(170)
        self.search.textChanged.connect(controller.set_search)
        self.status = QComboBox()
        for text, _ in STATUS_FILTERS:
            self.status.addItem(text)
        self.status.setFixedWidth(140)
        self.status.setStyleSheet("padding-left: 8px;")
        self.status.currentIndexChanged.connect(controller.set_status_index)
        clear = QPushButton("Bersihkan")
        clear.setStyleSheet("padding: 7px 10px;")
        clear.setToolTip("Kosongkan tabel (data tetap tersimpan di _log\\diterima_YYYY-MM-DD.txt)")
        clear.clicked.connect(controller.clear)
        live = QLabel()
        live.setPixmap(dot_pixmap(theme.GREEN, 10))
        live_text = QLabel(f"Auto-refresh ({REFRESH_MS // 1000}s)")
        live_text.setStyleSheet(f"color: {theme.GREEN}; font-size: 8.5pt;")
        self.toggle = ToggleSwitch()
        self.toggle.setChecked(controller.auto_refresh)
        self.toggle.setToolTip("Tabel diperbarui setiap 3 detik. Matikan untuk menahan tampilan.")
        self.toggle.toggled.connect(controller.set_auto_refresh)
        header.addWidget(self.search)
        header.addWidget(self.status)
        header.addWidget(clear)
        for b in extra_buttons:
            header.addWidget(b)
        header.addSpacing(4)
        header.addWidget(live)
        header.addWidget(live_text)
        header.addWidget(self.toggle)
        self.body.addLayout(header)

        self.view = QTableView()
        self.view.setModel(controller.proxy)
        self.view.setItemDelegateForColumn(COL_STATUS, StatusDelegate(self.view))
        self.view.setItemDelegateForColumn(COL_ACTION, ActionDelegate(self.view))
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.view.setShowGrid(False)
        self.view.setWordWrap(False)
        self.view.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.view.verticalHeader().setVisible(False)
        self.view.verticalHeader().setDefaultSectionSize(30)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(COL_TIME, Qt.SortOrder.DescendingOrder)
        self.view.setMouseTracking(True)
        hh = self.view.horizontalHeader()
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        widths = {COL_TIME: 84, COL_FROM: 92, COL_CODE: 96, COL_STATUS: 130, COL_ACTION: 48}
        for col in range(len(COLUMNS)):
            if col in (COL_ORIGINAL, COL_NAME):
                hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
            else:
                hh.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
                self.view.setColumnWidth(col, widths[col])
        self.view.clicked.connect(self._clicked)
        self.view.doubleClicked.connect(self._activated)
        self.body.addWidget(self.view, 1)
        controller.changed.connect(self._sync)

    def _row_at(self, proxy_index) -> dict | None:
        return proxy_index.data(ROW_ROLE) if proxy_index.isValid() else None

    def _clicked(self, index) -> None:
        if index.column() == COL_ACTION:
            self._activated(index)

    def _activated(self, index) -> None:
        row = self._row_at(index)
        if row:
            self.rowActivated.emit(row)

    def _sync(self) -> None:
        c = self.controller
        for widget, setter, value in ((self.search, self.search.setText, c.search),
                                      (self.status, self.status.setCurrentIndex, c.status_index),
                                      (self.toggle, self.toggle.setChecked, c.auto_refresh)):
            widget.blockSignals(True)
            if (widget.text() if widget is self.search else
                    widget.currentIndex() if widget is self.status else widget.isChecked()) != value:
                setter(value)
            widget.blockSignals(False)
        self.toggle.update()
