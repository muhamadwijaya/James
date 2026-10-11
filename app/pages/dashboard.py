"""The Dashboard page -- a faithful rebuild of the reference design."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QComboBox, QButtonGroup, QSizePolicy,
)

from ..theme import Color, Font
from .. import brand, icons
from ..widgets.common import Card, CardHeader, VSep, HSep, make_font, label
from ..widgets.buttons import (
    GhostButton, PrimaryButton, QuickTile, FilterPill, ListItem,
)
from ..widgets.console import ConsoleView


# --------------------------------------------------------------------------- #
#  small helpers
# --------------------------------------------------------------------------- #
def _kv_row(key: str, value: str, *, value_color: str = Color.TEXT_DIM,
            dot: bool = False, key_w: int = 92) -> QWidget:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(10)
    k = label(key, size=11, color=Color.TEXT_MUTED)
    k.setFixedWidth(key_w)
    lay.addWidget(k)
    if dot:
        d = QLabel()
        d.setFixedSize(9, 9)
        d.setStyleSheet(f"background: {Color.GREEN_DOT}; border-radius: 4px;")
        lay.addWidget(d)
    v = label(value, size=11, weight=QFont.Medium, color=value_color)
    lay.addWidget(v)
    lay.addStretch(1)
    return w


class TabButton(QWidget):
    """A single tab in the RFID tool tab-bar."""

    def __init__(self, text: str, group, idx: int, active=False):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        self._active = active
        self._idx = idx
        self._group = group
        self.setMinimumHeight(48)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self._lbl = QLabel(text)
        self._lbl.setAlignment(Qt.AlignCenter)
        self._lbl.setFont(make_font(Font.UI, 11, QFont.DemiBold))
        lay.addWidget(self._lbl, 1)
        self._bar = QFrame()
        self._bar.setFixedHeight(3)
        lay.addWidget(self._bar)
        self._render()

    def mousePressEvent(self, e):
        self._group.select(self._idx)

    def set_active(self, v: bool):
        self._active = v
        self._render()

    def _render(self):
        if self._active:
            self._lbl.setStyleSheet(
                f"color: {Color.GREEN}; background: transparent;")
            self._bar.setStyleSheet(
                f"background: {Color.GREEN}; border-top-left-radius:2px;"
                f" border-top-right-radius:2px;")
            self.setStyleSheet(
                f"background: {Color.GREEN_GLOW}; border-top-left-radius:10px;"
                f" border-top-right-radius:10px;")
        else:
            self._lbl.setStyleSheet(
                f"color: {Color.TEXT_DIM}; background: transparent;")
            self._bar.setStyleSheet("background: transparent;")
            self.setStyleSheet("background: transparent;")


class TabBar(QWidget):
    def __init__(self, labels, active=1):
        super().__init__()
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self._tabs = []
        for i, t in enumerate(labels):
            tab = TabButton(t, self, i, active=(i == active))
            self._tabs.append(tab)
            lay.addWidget(tab, 1)
        self._active = active

    def select(self, idx: int):
        if idx == self._active:
            return
        self._tabs[self._active].set_active(False)
        self._tabs[idx].set_active(True)
        self._active = idx


# --------------------------------------------------------------------------- #
#  dashboard
# --------------------------------------------------------------------------- #
class Dashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 18)
        root.setSpacing(15)

        row1 = QHBoxLayout()
        row1.setSpacing(16)
        row1.addWidget(self._device_card(), 57)
        row1.addWidget(self._quick_card(), 43)
        root.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(16)
        row2.addWidget(self._rfid_card(), 60)
        row2.addWidget(self._console_card(), 40)
        root.addLayout(row2)

        root.addWidget(self._logs_card())
        root.addStretch(1)

    # ---- Device Connection ------------------------------------------------ #
    def _device_card(self) -> Card:
        card = Card()
        b = card.body()
        b.addWidget(CardHeader("link", "Device Connection"))

        row = QHBoxLayout()
        row.setSpacing(24)

        img = QLabel()
        img.setPixmap(brand.device_pixmap(150, 110))
        img.setFixedSize(160, 120)
        img.setAlignment(Qt.AlignCenter)
        row.addWidget(img, alignment=Qt.AlignVCenter)

        info = QVBoxLayout()
        info.setSpacing(9)
        info.addWidget(_kv_row("Status", "Connected", value_color=Color.GREEN,
                               dot=True))
        info.addWidget(_kv_row("Device", "Proxmark3 RDV4", value_color=Color.TEXT_DIM))
        info.addWidget(_kv_row("Serial", "PM3-12345678", value_color=Color.TEXT_DIM))
        info.addWidget(_kv_row("Interface", "USB (COM5)", value_color=Color.TEXT_DIM))
        info.addWidget(_kv_row("Firmware", "4.19341", value_color=Color.TEXT_DIM))
        row.addLayout(info)
        row.addStretch(1)

        btns = QVBoxLayout()
        btns.setSpacing(12)
        dc = GhostButton("Disconnect", "plug", accent=True)
        dc.setFixedWidth(180)
        rs = GhostButton("Restart", "refresh", accent=False)
        rs.setFixedWidth(180)
        btns.addStretch(1)
        btns.addWidget(dc)
        btns.addWidget(rs)
        btns.addStretch(1)
        row.addLayout(btns)

        b.addLayout(row)
        return card

    # ---- Quick Tools ------------------------------------------------------ #
    def _quick_card(self) -> Card:
        card = Card()
        b = card.body()
        b.addWidget(CardHeader("bolt", "Quick Tools"))
        grid = QHBoxLayout()
        grid.setSpacing(14)
        tiles = [
            ("scan", "Identify Card", "Read card info"),
            ("shield", "Read UID", "Get UID only"),
            ("refresh2", "Raw Command", "Send custom cmd"),
            ("sniff", "Sniff Mode", "Capture traffic"),
        ]
        for name, t, s in tiles:
            grid.addWidget(QuickTile(name, t, s))
        b.addLayout(grid)
        return card

    # ---- RFID / NFC Tools ------------------------------------------------- #
    def _rfid_card(self) -> Card:
        card = Card()
        b = card.body()
        b.addWidget(CardHeader("radio", "RFID / NFC Tools"))

        tabs = TabBar(
            ["LF (125 kHz)", "HF (13.56 MHz)", "iClass", "MIFARE",
             "Felica", "NFC"], active=1)
        b.addWidget(tabs)

        # inner panel with 3 columns
        panel = QFrame()
        panel.setObjectName("InnerPanel")
        panel.setStyleSheet(
            f"#InnerPanel {{ background: {Color.CARD_ALT};"
            f" border: 1px solid {Color.BORDER_SOFT}; border-radius: 12px; }}")
        pl = QHBoxLayout(panel)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(0)
        pl.addWidget(self._mifare_list(), 27)
        pl.addWidget(VSep())
        pl.addWidget(self._read_form(), 35)
        pl.addWidget(VSep())
        pl.addWidget(self._hex_view(), 38)
        b.addWidget(panel, 1)
        return card

    def _mifare_list(self) -> QWidget:
        w = QWidget()
        w.setMinimumWidth(176)
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 18, 12, 18)
        lay.setSpacing(4)
        title = label("MIFARE Classic", size=12, weight=QFont.Bold,
                      color=Color.TEXT)
        lay.addWidget(title)
        lay.addSpacing(8)

        group = QButtonGroup(w)
        group.setExclusive(True)
        items = [
            ("scan", "Read Card"),
            ("write", "Write Block"),
            ("dump", "Dump"),
            ("restore", "Restore"),
            ("format", "Format"),
            ("keyA", "Auth (A Key)"),
            ("keyB", "Auth (B Key)"),
        ]
        for i, (ic, txt) in enumerate(items):
            it = ListItem(ic, txt)
            group.addButton(it, i)
            lay.addWidget(it)
            if i == 0:
                it.setChecked(True)
        lay.addStretch(1)
        return w

    def _read_form(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(14)

        lay.addWidget(label("Read Card", size=13, weight=QFont.Bold,
                            color=Color.GREEN))

        for lbl_text in ("Sector:", "Sector:"):
            r = QHBoxLayout()
            r.setSpacing(12)
            lab = label(lbl_text, size=11, color=Color.TEXT_DIM)
            lab.setFixedWidth(58)
            r.addWidget(lab)
            combo = QComboBox()
            combo.addItems([str(i) for i in range(16)])
            combo.setMinimumWidth(110)
            r.addWidget(combo, 1)
            lay.addLayout(r)

        read = PrimaryButton("Read Block", "play")
        lay.addWidget(read)
        lay.addSpacing(6)

        lay.addWidget(label("Card Information", size=12, weight=QFont.DemiBold,
                            color=Color.TEXT))
        info = QVBoxLayout()
        info.setSpacing(9)
        for k, v in [("UID", "04 A2 6B 3F"), ("Type", "MIFARE Classic 1K"),
                     ("Size", "1024 bytes"), ("ATQA", "0x4400"),
                     ("SAK", "0x08")]:
            info.addWidget(_kv_row(k, v, value_color=Color.TEXT_DIM, key_w=64))
        lay.addLayout(info)
        lay.addStretch(1)
        return w

    def _hex_view(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(12)

        head = QHBoxLayout()
        head.addWidget(label("Data (Block 0)", size=12, weight=QFont.DemiBold,
                            color=Color.TEXT))
        head.addStretch(1)
        head.addWidget(self._hex_toggle())
        lay.addLayout(head)

        # hex block
        hexwrap = QFrame()
        hexwrap.setObjectName("HexWrap")
        hexwrap.setStyleSheet(
            f"#HexWrap {{ background: {Color.CONSOLE_BG};"
            f" border: 1px solid {Color.BORDER_SOFT}; border-radius: 10px; }}")
        hl = QVBoxLayout(hexwrap)
        hl.setContentsMargins(16, 14, 16, 14)
        hl.setSpacing(8)
        for addr in ("000", "010", "020", "030"):
            line = QLabel()
            line.setTextFormat(Qt.RichText)
            line.setFont(make_font(Font.MONO, 11))
            bytes_html = "&nbsp;".join(
                f"<span style='color:{Color.TEXT_DIM}'>00</span>" for _ in range(11))
            line.setText(
                f"<span style='color:{Color.TEXT_FAINT}'>{addr}:</span>"
                f"&nbsp;&nbsp;{bytes_html}")
            hl.addWidget(line)
        lay.addWidget(hexwrap)

        # ascii block
        asciiwrap = QFrame()
        asciiwrap.setObjectName("AsciiWrap")
        asciiwrap.setStyleSheet(
            f"#AsciiWrap {{ background: {Color.CONSOLE_BG};"
            f" border: 1px solid {Color.BORDER_SOFT}; border-radius: 10px; }}")
        al = QVBoxLayout(asciiwrap)
        al.setContentsMargins(16, 14, 16, 14)
        al.setSpacing(8)
        at = label("ASCII", family=Font.MONO, size=11, color=Color.TEXT_DIM)
        al.addWidget(at)
        for _ in range(3):
            dots = label("." * 46, family=Font.MONO, size=11,
                         color=Color.TEXT_MUTED)
            al.addWidget(dots)
        lay.addWidget(asciiwrap, 1)
        return w

    def _hex_toggle(self) -> QWidget:
        w = QFrame()
        w.setStyleSheet(
            f"background: {Color.GREEN}; border-radius: 7px;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(8, 5, 10, 5)
        lay.setSpacing(6)
        ic = QLabel()
        ic.setPixmap(icons.pixmap("hexview", 15, "#042016"))
        lay.addWidget(ic)
        t = QLabel("Hex")
        t.setFont(make_font(Font.UI, 10, QFont.DemiBold))
        t.setStyleSheet("color: #042016; background: transparent;")
        lay.addWidget(t)
        return w

    # ---- Command Console -------------------------------------------------- #
    def _console_card(self) -> Card:
        card = Card()
        b = card.body()
        b.addWidget(CardHeader("terminal", "Command Console"))
        b.addWidget(ConsoleView(), 1)
        return card

    # ---- Live Logs -------------------------------------------------------- #
    def _logs_card(self) -> Card:
        card = Card()
        b = card.body()

        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(CardHeader("file", "Live Logs"))
        head.addStretch(1)
        group = QButtonGroup(card)
        group.setExclusive(True)
        for i, name in enumerate(["All", "Info", "Cmd", "Resp", "Error"]):
            pill = FilterPill(name)
            group.addButton(pill, i)
            head.addWidget(pill)
            if i == 0:
                pill.setChecked(True)
        clear = FilterPill("  Clear")
        clear.setCheckable(False)
        clear.setIcon(icons.icon("clear", 14, Color.TEXT_MUTED))
        head.addWidget(clear)
        b.addLayout(head)

        b.addWidget(self._logs_table())
        return card

    def _logs_table(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # header row
        hdr = QWidget()
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(4, 0, 4, 8)
        hl.setSpacing(0)
        for text, wdt in [("Time", 120), ("Source", 110), ("Message", 0)]:
            l = label(text, size=10, weight=QFont.DemiBold, color=Color.TEXT_FAINT)
            if wdt:
                l.setFixedWidth(wdt)
            hl.addWidget(l, 0 if wdt else 1)
        lay.addWidget(hdr)
        lay.addWidget(HSep())

        rows = [
            ("10:24:13", "INFO", Color.TEXT_CYAN,
             "[USB] Device connected: Proxmark3 RDV4 (COM5)", Color.TEXT_DIM, False),
            ("10:24:18", "CMD", Color.TEXT_DIM, "> hw status", Color.GREEN, True),
            ("10:24:18", "RESP", Color.GREEN,
             "[+] Proxmark3 RDV4 | Firmware 4.19341", Color.TEXT_DIM, False),
            ("10:24:32", "CMD", Color.TEXT_DIM, "> hf 14a search", Color.GREEN, True),
            ("10:24:32", "RESP", Color.GREEN,
             "[+] Found 1 tag: UID 04 A2 6B 3F (MIFARE Classic)", Color.TEXT_DIM, False),
            ("10:24:45", "CMD", Color.TEXT_DIM, "> hf mf rdbl 0 0", Color.GREEN, True),
            ("10:24:45", "RESP", Color.GREEN,
             "[+] Block 0 read successfully", Color.TEXT_DIM, False),
        ]
        for time, src, src_col, msg, msg_col, mono in rows:
            lay.addWidget(self._log_row(time, src, src_col, msg, msg_col, mono))
        return w

    def _log_row(self, time, src, src_col, msg, msg_col, mono) -> QWidget:
        row = QFrame()
        row.setStyleSheet("QFrame:hover { background: %s; border-radius:6px; }"
                          % Color.TILE)
        rl = QHBoxLayout(row)
        rl.setContentsMargins(4, 5, 4, 5)
        rl.setSpacing(0)
        t = label(time, family=Font.MONO, size=10, color=Color.TEXT_DIM)
        t.setFixedWidth(120)
        rl.addWidget(t)
        s = label(src, family=Font.MONO, size=10, weight=QFont.DemiBold,
                  color=src_col)
        s.setFixedWidth(110)
        rl.addWidget(s)
        m = label(msg, family=Font.MONO, size=10,
                  weight=QFont.Medium if mono else QFont.Normal, color=msg_col)
        rl.addWidget(m, 1)
        return row
