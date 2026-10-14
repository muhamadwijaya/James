"""Custom widgets for the FRT Cam dashboard."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

import icons
import theme


def qcolor(hex_color: str, alpha: float = 1.0) -> QColor:
    c = QColor(hex_color)
    c.setAlphaF(alpha)
    return c


def human_size(n: float) -> str:
    if n < 1024:
        return f"{int(n)} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"


class IconBox(QWidget):
    """Rounded square with an icon: solid (gradient + white icon) or soft (tinted + colored icon)."""

    def __init__(self, icon_name: str, color: str, size: int = 40, solid: bool = False,
                 icon_size: int | None = None, parent=None) -> None:
        super().__init__(parent)
        self._icon = icon_name
        self._color = color
        self._solid = solid
        self._icon_size = icon_size or int(size * 0.5)
        self.setFixedSize(size, size)

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = r.width() * 0.26
        if self._solid:
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            g.setColorAt(0, qcolor(self._color).lighter(125))
            g.setColorAt(1, qcolor(self._color).darker(115))
            p.setBrush(QBrush(g))
            p.setPen(QPen(qcolor(self._color).lighter(140), 1))
            icon_color = "#ffffff"
        else:
            p.setBrush(qcolor(self._color, 0.14))
            p.setPen(QPen(qcolor(self._color, 0.35), 1))
            icon_color = self._color
        p.drawRoundedRect(r, radius, radius)
        pm = icons.pixmap(self._icon, icon_color, self._icon_size)
        s = self._icon_size
        p.drawPixmap(int((self.width() - s) / 2), int((self.height() - s) / 2), pm)


class Card(QFrame):
    """Rounded panel with an optional header (icon box, title, subtitle, right-side widgets)."""

    def __init__(self, title: str | None = None, subtitle: str | None = None, icon_name: str | None = None,
                 icon_color: str = theme.BLUE, margins=(16, 12, 16, 14), parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(*margins)
        self.body.setSpacing(12)
        self.header_right: QHBoxLayout | None = None
        self.title_label: QLabel | None = None
        if title is not None:
            header = QHBoxLayout()
            header.setSpacing(12)
            if icon_name:
                header.addWidget(IconBox(icon_name, icon_color, 40))
            texts = QVBoxLayout()
            texts.setSpacing(1)
            self.title_label = QLabel(title)
            self.title_label.setObjectName("cardTitle")
            texts.addWidget(self.title_label)
            if subtitle:
                sub = QLabel(subtitle)
                sub.setObjectName("cardSubtitle")
                texts.addWidget(sub)
            header.addLayout(texts)
            header.addStretch(1)
            self.header_right = QHBoxLayout()
            self.header_right.setSpacing(8)
            header.addLayout(self.header_right)
            self.body.addLayout(header)


class StatusBox(QFrame):
    """'● Terhubung ~' with an optional second line; colors follow the state."""

    def __init__(self, compact: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("statusBox")
        self._compact = compact
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 6 if compact else 7, 14, 6 if compact else 7)
        outer.setSpacing(1)
        row = QHBoxLayout()
        row.setSpacing(8)
        self._dot = QLabel()
        self._title = QLabel()
        self._title.setStyleSheet("font-weight: 600;")
        self._pulse = QLabel()
        row.addWidget(self._dot)
        row.addWidget(self._title)
        row.addWidget(self._pulse)
        row.addStretch(1)
        outer.addLayout(row)
        self._subtitle = QLabel()
        self._subtitle.setStyleSheet("font-size: 8pt;")
        if not compact:
            outer.addWidget(self._subtitle)
        self.set_state(theme.DIM, "Tidak aktif", "")

    def set_state(self, color: str, title: str, subtitle: str = "") -> None:
        self._dot.setPixmap(_dot_pixmap(color, 12 if not self._compact else 11, glow=True))
        self._title.setText(title)
        self._title.setStyleSheet(f"font-weight: 600; color: {color};")
        self._pulse.setPixmap(icons.pixmap("activity", color, 18))
        self._subtitle.setText(subtitle)
        self._subtitle.setStyleSheet(f"font-size: 8pt; color: {color};")
        self.setStyleSheet(f"#statusBox {{ background: {theme.rgba(color, 0.08)}; "
                           f"border: 1px solid {theme.rgba(color, 0.45)}; border-radius: 9px; }}")

    def title(self) -> str:
        return self._title.text()


def _dot_pixmap(color: str, size: int, glow: bool = False) -> QPixmap:
    dpr = 2.0
    pm = QPixmap(int(size * dpr), int(size * dpr))
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    c = QPointF(size * dpr / 2, size * dpr / 2)
    if glow:
        g = QRadialGradient(c, size * dpr / 2)
        g.setColorAt(0, qcolor(color, 0.55))
        g.setColorAt(1, qcolor(color, 0.0))
        p.setBrush(QBrush(g))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(c, size * dpr / 2, size * dpr / 2)
    p.setBrush(qcolor(color))
    p.setPen(Qt.PenStyle.NoPen)
    radius = size * dpr * (0.3 if glow else 0.5)
    p.drawEllipse(c, radius, radius)
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def dot_pixmap(color: str, size: int = 8) -> QPixmap:
    return _dot_pixmap(color, size)


class StateBadge(QLabel):
    """Outlined '● Berjalan' badge next to the start/stop buttons."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("stateButton")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(54)
        self.set_state(theme.DIM, "Berhenti")

    def set_state(self, color: str, text: str) -> None:
        self._text = text
        self.setText(f'<span style="color:{color}; font-size:14pt;">&#9679;</span>&nbsp;&nbsp;'
                     f'<span style="color:{color};">{text}</span>')
        self.setStyleSheet(f"#stateButton {{ border: 1px solid {theme.rgba(color, 0.75)}; border-radius: 9px; "
                           f"background: {theme.rgba(color, 0.07)}; font-size: 11pt; font-weight: 600; }}")

    def plain_text(self) -> str:
        return self._text


class StatCard(QFrame):
    """Counter tile: icon, title, big number, subtitle and faint bars of recent activity."""

    def __init__(self, title: str, icon_name: str, color: str, parent=None) -> None:
        super().__init__(parent)
        self._color = color
        self._series: list[int] = []
        self.setMinimumHeight(88)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(150)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 12, 10, 10)
        layout.setSpacing(12)
        layout.addWidget(IconBox(icon_name, color, 44, solid=True, icon_size=23), 0, Qt.AlignmentFlag.AlignTop)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        self._title = QLabel(title)
        self._title.setStyleSheet("font-size: 9.5pt; font-weight: 600;")
        self.value_label = QLabel("0")
        self.value_label.setStyleSheet("font-size: 17pt; font-weight: 700;")
        self.subtitle_label = QLabel("")
        self.subtitle_label.setStyleSheet(f"color: {color}; font-size: 8pt;")
        texts.addWidget(self._title)
        texts.addWidget(self.value_label)
        texts.addWidget(self.subtitle_label)
        texts.addStretch(1)
        layout.addLayout(texts, 1)

    def set_data(self, value: int, subtitle: str, series: list[int] | None = None) -> None:
        self.value_label.setText(f"{value:,}".replace(",", "."))
        self.subtitle_label.setText(subtitle)
        if series is not None and series != self._series:
            self._series = list(series)
            self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        g = QLinearGradient(r.topLeft(), r.bottomRight())
        g.setColorAt(0, qcolor(self._color, 0.20))
        g.setColorAt(0.55, qcolor(theme.CARD_2, 0.95))
        g.setColorAt(1, qcolor(theme.CARD, 1.0))
        p.setBrush(QBrush(g))
        p.setPen(QPen(qcolor(self._color, 0.38), 1))
        p.drawRoundedRect(r, 12, 12)

        # faint bars on the right: activity of the last minutes
        series = self._series or [0] * 16
        n = len(series)
        area = QRectF(r.width() * 0.56, r.height() * 0.38, r.width() * 0.40, r.height() * 0.50)
        peak = max(max(series), 1)
        step = area.width() / n
        bar_w = max(2.0, step * 0.55)
        p.setPen(Qt.PenStyle.NoPen)
        for i, v in enumerate(series):
            # empty minutes still get a low bar so the tile reads as a small chart
            h = area.height() * (0.18 + 0.82 * v / peak if v else 0.10 + 0.08 * ((i * 7) % 5) / 4)
            alpha = (0.16 if v else 0.08) + 0.25 * (i / max(n - 1, 1))
            p.setBrush(qcolor(self._color, alpha))
            p.drawRoundedRect(QRectF(area.left() + i * step, area.bottom() - h, bar_w, h), 1.5, 1.5)


class ActivityChart(QWidget):
    """Bars of files per second for the last minute."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._values: list[int] = [0] * 60
        self.setMinimumHeight(44)

    def set_values(self, values: list[int]) -> None:
        if values != self._values:
            self._values = list(values)
            self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        n = len(self._values)
        peak = max(max(self._values), 1)
        step = r.width() / n
        bar_w = max(1.5, step * 0.5)
        p.setPen(QPen(qcolor(theme.BORDER), 1))
        p.drawLine(QPointF(r.left(), r.bottom()), QPointF(r.right(), r.bottom()))
        p.setPen(Qt.PenStyle.NoPen)
        for i, v in enumerate(self._values):
            if v <= 0:
                h = 2.0
                p.setBrush(qcolor(theme.BLUE, 0.18))
            else:
                h = max(4.0, (r.height() - 2) * v / peak)
                g = QLinearGradient(QPointF(0, r.bottom() - h), QPointF(0, r.bottom()))
                g.setColorAt(0, qcolor("#5aa2ff"))
                g.setColorAt(1, qcolor(theme.BLUE_DARK))
                p.setBrush(QBrush(g))
            p.drawRoundedRect(QRectF(r.left() + i * step + (step - bar_w) / 2, r.bottom() - h, bar_w, h), 1, 1)


class ToggleSwitch(QAbstractButton):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(40, 22)

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(40, 22)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        on = self.isChecked()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qcolor(theme.BLUE if on else "#2a3d60", 1.0 if self.isEnabled() else 0.5))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 6
        x = r.right() - d - 3 if on else r.left() + 3
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, r.top() + 3, d, d))


class TransferCard(QFrame):
    """'Transfer Saat Ini': latest file transfer with progress, size and speed."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 10)
        layout.setSpacing(4)
        head = QLabel("Transfer Saat Ini")
        head.setStyleSheet("font-size: 9pt;")
        layout.addWidget(head)
        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(IconBox("file_text", theme.BLUE, 32, solid=True, icon_size=17), 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(4)
        self.name_label = QLabel("Belum ada transfer")
        self.name_label.setStyleSheet("font-size: 8pt;")
        self.name_label.setMinimumWidth(10)
        bar_row = QHBoxLayout()
        bar_row.setSpacing(10)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.percent_label = QLabel("")
        self.percent_label.setStyleSheet(f"color: {theme.CYAN}; font-weight: 600;")
        self.percent_label.setMinimumWidth(36)
        bar_row.addWidget(self.progress, 1)
        bar_row.addWidget(self.percent_label)
        info_row = QHBoxLayout()
        self.size_label = QLabel("")
        self.size_label.setObjectName("hint")
        self.speed_label = QLabel("")
        self.speed_label.setObjectName("hint")
        info_row.addWidget(self.size_label)
        info_row.addStretch(1)
        info_row.addWidget(self.speed_label)
        col.addWidget(self.name_label)
        col.addLayout(bar_row)
        col.addLayout(info_row)
        row.addLayout(col, 1)
        layout.addLayout(row)
        self._full_name = ""

    def set_transfer(self, name: str, done_bytes: int, total: int, ms: int, state: str, extra: int = 0) -> None:
        self._full_name = name + (f"   (+{extra} lainnya)" if extra else "")
        self._elide()
        self.name_label.setToolTip(name)
        finished = state in ("done", "error")
        if total and total > 0:
            pct = 100 if state == "done" else int(min(done_bytes, total) * 100 / total)
            self.progress.setRange(0, 100)
            self.progress.setValue(pct)
            self.percent_label.setText(f"{pct}%")
            self.size_label.setText(f"{human_size(done_bytes)} / {human_size(total)}")
        elif finished:
            self.progress.setRange(0, 100)
            self.progress.setValue(100 if state == "done" else 0)
            self.percent_label.setText("100%" if state == "done" else "")
            self.size_label.setText(f"{human_size(done_bytes)} / {human_size(done_bytes)}")
        else:
            self.progress.setRange(0, 0)  # size unknown while receiving: busy indicator
            self.percent_label.setText("")
            self.size_label.setText(f"{human_size(done_bytes)} diterima")
        speed = done_bytes / max(ms, 1) * 1000.0
        self.speed_label.setText("Gagal" if state == "error" else f"{human_size(speed)}/s")
        self.speed_label.setStyleSheet(f"color: {theme.RED};" if state == "error" else "")

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        if self._full_name:
            fm = QFontMetrics(self.name_label.font())
            width = max(40, self.name_label.width())
            self.name_label.setText(fm.elidedText(self._full_name, Qt.TextElideMode.ElideMiddle, width))


class ImageView(QWidget):
    """Shows a pixmap fitted to the widget; wheel/buttons zoom, drag pans, double-click emits."""

    doubleClicked = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._message = "Belum ada foto tersimpan"
        self._zoom = 1.0
        self._offset = QPointF(0, 0)
        self._drag_start: QPointF | None = None
        self.setMinimumSize(240, 160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_pixmap(self, pixmap: QPixmap | None, message: str = "") -> None:
        self._pixmap = pixmap
        self._message = message
        self._zoom = 1.0
        self._offset = QPointF(0, 0)
        self.update()

    def pixmap(self) -> QPixmap | None:
        return self._pixmap

    def zoom_by(self, factor: float) -> None:
        if self._pixmap is None:
            return
        self._zoom = max(1.0, min(8.0, self._zoom * factor))
        if self._zoom == 1.0:
            self._offset = QPointF(0, 0)
        self.update()

    def _target_rect(self) -> QRectF:
        pw, ph = self._pixmap.width() / self._pixmap.devicePixelRatio(), self._pixmap.height() / self._pixmap.devicePixelRatio()
        base = min(self.width() / pw, self.height() / ph)
        scale = base * self._zoom
        w, h = pw * scale, ph * scale
        max_dx = max(0.0, (w - self.width()) / 2)
        max_dy = max(0.0, (h - self.height()) / 2)
        self._offset = QPointF(max(-max_dx, min(max_dx, self._offset.x())), max(-max_dy, min(max_dy, self._offset.y())))
        return QRectF((self.width() - w) / 2 + self._offset.x(), (self.height() - h) / 2 + self._offset.y(), w, h)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect())
        path = QPainterPath()
        path.addRoundedRect(r, 10, 10)
        p.setClipPath(path)
        p.fillRect(r, QColor("#060d1a"))
        if self._pixmap is None or self._pixmap.isNull():
            p.setPen(qcolor(theme.MUTED))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, self._message)
            return
        p.drawPixmap(self._target_rect(), self._pixmap, QRectF(self._pixmap.rect()))

    def wheelEvent(self, event) -> None:  # noqa: N802
        self.zoom_by(1.15 if event.angleDelta().y() > 0 else 1 / 1.15)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._zoom > 1.0:
            self._drag_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_start is not None:
            delta = event.position() - self._drag_start
            self._drag_start = event.position()
            self._offset += delta
            self.update()

    def mouseReleaseEvent(self, _event) -> None:  # noqa: N802
        self._drag_start = None
        self.unsetCursor()

    def mouseDoubleClickEvent(self, _event) -> None:  # noqa: N802
        self.doubleClicked.emit()


class FullscreenViewer(QDialog):
    """Full screen photo; Esc, double-click or the X button closes it."""

    def __init__(self, pixmap: QPixmap, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setStyleSheet("QDialog { background: #000000; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        bar.setContentsMargins(16, 10, 16, 0)
        caption = QLabel(title)
        caption.setStyleSheet("color: #e8eef8; font-weight: 600;")
        close = QPushButton()
        close.setObjectName("closeButton")
        close.setIcon(icons.icon("close", "#ffffff", 18))
        close.clicked.connect(self.accept)
        bar.addWidget(caption)
        bar.addStretch(1)
        bar.addWidget(close)
        layout.addLayout(bar)
        self.view = ImageView()
        self.view.set_pixmap(pixmap)
        self.view.doubleClicked.connect(self.accept)
        layout.addWidget(self.view, 1)


def hline() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {theme.BORDER};")
    return line


def bold_font(size: float) -> QFont:
    f = QFont()
    f.setPointSizeF(size)
    f.setBold(True)
    return f
