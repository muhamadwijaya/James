"""Command console output + input (presentation only, with canned data)."""

from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, QFrame,
)

from ..theme import Color, Font
from .buttons import IconButton
from .common import make_font


# Canned console transcript matching the reference screenshot.
_LINES = [
    ("cmd", "> hw status"),
    ("ok", "[+] Proxmark3 RDV4"),
    ("ok", "[+] Firmware 4.19341"),
    ("ok", "[+] FPGA      0x4"),
    ("ok", "[+] UniqueID      0x12345678"),
    ("ok", "[+] Target: none selected"),
    ("blank", ""),
    ("cmd", "> hf 14a 3"),
    ("star", "[*]   Searching for ISO14443-A tag..."),
    ("star", "[*]   UID: 04 A2 6B 3F"),
    ("star", "[*]   ATQA: 0x4400   SAK: 0x08"),
    ("star", "[*]   Type: MIFARE Classic 1K"),
    ("blank", ""),
    ("cmd", "> hf mf rdbl 0 0"),
    ("star", "[*]   Reading block 0..."),
    ("star", "[*]   Data: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00"),
]


def _render_html() -> str:
    def esc(s):
        return escape(s).replace(" ", "&nbsp;")

    out = []
    for kind, text in _LINES:
        if kind == "blank":
            out.append("<div style='line-height:115%'>&nbsp;</div>")
            continue
        if kind == "cmd":
            # colour the leading '>' + command verb
            parts = text.split(" ")
            gt = f"<span style='color:{Color.GREEN}'>&gt;</span>"
            rest = "&nbsp;".join(esc(p) for p in parts[1:])
            html = f"{gt}&nbsp;<span style='color:{Color.GREEN}'>{rest}</span>"
        elif kind == "ok":
            marker = f"<span style='color:{Color.CONSOLE_STAR}'>[+]</span>"
            html = marker + "&nbsp;" + f"<span style='color:{Color.CONSOLE_TEXT}'>{esc(text[3:].strip())}</span>"
        else:  # star
            marker = f"<span style='color:{Color.CONSOLE_STAR}'>[*]</span>"
            html = marker + "&nbsp;" + f"<span style='color:{Color.CONSOLE_TEXT}'>{esc(text[3:].strip())}</span>"
        out.append(f"<div style='line-height:140%'>{html}</div>")
    # trailing prompt with block cursor
    out.append(
        f"<div style='line-height:140%'><span style='color:{Color.GREEN}'>&gt;</span>"
        f"&nbsp;<span style='background:{Color.GREEN};color:{Color.GREEN}'>&nbsp;&nbsp;</span></div>")
    return "".join(out)


class ConsoleView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(14)

        # output surface
        wrap = QFrame()
        wrap.setObjectName("ConsoleWrap")
        wrap.setStyleSheet(
            f"#ConsoleWrap {{ background: {Color.CONSOLE_BG};"
            f" border: 1px solid {Color.BORDER}; border-radius: 12px; }}")
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(6, 6, 6, 6)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFrameShape(QFrame.Shape.NoFrame)
        self.output.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.output.setFont(make_font(Font.MONO, 11))
        self.output.setStyleSheet(
            f"QTextEdit {{ background: transparent; border: none;"
            f" color: {Color.CONSOLE_TEXT}; padding: 8px 10px; }}")
        self.output.setHtml(_render_html())
        wl.addWidget(self.output)
        root.addWidget(wrap, 1)

        # input row
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Enter command...")
        self.input.setFont(make_font(Font.MONO, 11))
        self.input.setMinimumHeight(48)
        row.addWidget(self.input, 1)
        row.addWidget(IconButton("copy", tip="Copy output", size=48))
        row.addWidget(IconButton("expand", tip="Expand console", size=48))
        send = IconButton("send", tip="Send command", size=48, accent=True)
        send.clicked.connect(self._send)
        row.addWidget(send)
        root.addLayout(row)

    def _send(self):
        # presentation only: echo the typed command then clear.
        text = self.input.text().strip()
        if not text:
            return
        self.input.clear()
