"""TCP/IP client for the Kolektor: connect to a server/device (IP + port) and receive data.

Every message becomes one piece of data. A message may end with CR, LF, CRLF, ETX or NUL
(STX framing bytes are dropped); data that arrives without any terminator is taken as one
message after a short pause, so devices that send "raw" strings work too.
While running, a refused or lost connection is retried automatically.
"""
from __future__ import annotations

import re

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QAbstractSocket, QTcpSocket

CONNECT_TIMEOUT_MS = 5000
RETRY_MS = 3000
IDLE_FLUSH_MS = 300
MAX_PENDING = 64 * 1024
_SPLIT = re.compile(rb"[\r\n\x03\x00]")
_E = QAbstractSocket.SocketError
ERROR_TEXT = {
    _E.ConnectionRefusedError: "Koneksi ditolak (server belum aktif / port salah)",
    _E.RemoteHostClosedError: "Koneksi ditutup oleh server",
    _E.HostNotFoundError: "IP / nama server tidak ditemukan",
    _E.SocketTimeoutError: "Waktu tunggu habis",
    _E.NetworkError: "Jaringan terputus / tidak terjangkau",
}


def decode(raw: bytes) -> str:
    """Bytes -> clean text (UTF-8, falling back to Latin-1), control characters removed."""
    raw = raw.replace(b"\x02", b"")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    return "".join(ch for ch in text if ch >= " " or ch == "\t").strip()


class TcpReceiver(QObject):
    dataReceived = Signal(str)
    # state: "connecting" | "connected" | "retrying" | "stopped"
    statusChanged = Signal(str, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.host = ""
        self.port = 0
        self.active = False
        self.state = "stopped"
        self.message = ""
        self._buffer = b""

        self._socket = QTcpSocket(self)
        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.readyRead.connect(self._on_ready_read)
        self._socket.errorOccurred.connect(self._on_error)

        self._connect_timer = self._single_shot(CONNECT_TIMEOUT_MS, self._on_connect_timeout)
        self._retry_timer = self._single_shot(RETRY_MS, self._connect)
        self._idle_timer = self._single_shot(IDLE_FLUSH_MS, self._flush_pending)

    def _single_shot(self, ms: int, slot) -> QTimer:
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(ms)
        timer.timeout.connect(slot)
        return timer

    # ------------------------------------------------------------ public API
    def start(self, host: str, port: int) -> None:
        self.stop()
        self.host = host.strip()
        self.port = int(port)
        self.active = True
        self._connect()

    def stop(self) -> None:
        """Disconnect; data already received (even without terminator) is still delivered."""
        was_active = self.active
        self.active = False
        if was_active:
            self._drain()
        for timer in (self._connect_timer, self._retry_timer, self._idle_timer):
            timer.stop()
        self._flush_pending(deliver=was_active)
        self._abort_quietly()
        if was_active:
            self._set_state("stopped", "Tidak tersambung")

    def is_connected(self) -> bool:
        return self.state == "connected"

    # ------------------------------------------------------------ connection
    def _connect(self) -> None:
        if not self.active:
            return
        self._buffer = b""
        self._abort_quietly()
        self._set_state("connecting", f"Menyambung ke {self.host}:{self.port} ...")
        self._socket.connectToHost(self.host, self.port)
        self._connect_timer.start()

    def _abort_quietly(self) -> None:
        self._socket.blockSignals(True)
        self._socket.abort()
        self._socket.blockSignals(False)

    def _on_connected(self) -> None:
        self._connect_timer.stop()
        self._socket.setSocketOption(QAbstractSocket.SocketOption.KeepAliveOption, 1)
        self._socket.setSocketOption(QAbstractSocket.SocketOption.LowDelayOption, 1)
        self._set_state("connected", f"Terhubung ke {self.host}:{self.port}")

    def _on_connect_timeout(self) -> None:
        if self.active and self._socket.state() != QAbstractSocket.SocketState.ConnectedState:
            self._schedule_retry(f"Tidak ada jawaban dari {self.host}:{self.port}")

    def _on_error(self, error) -> None:
        if self.active:
            self._schedule_retry(ERROR_TEXT.get(error) or self._socket.errorString())

    def _on_disconnected(self) -> None:
        if self.active:
            self._schedule_retry("Koneksi ditutup oleh server")

    def _schedule_retry(self, reason: str) -> None:
        self._connect_timer.stop()
        self._drain()
        self._idle_timer.stop()
        self._flush_pending()
        self._abort_quietly()
        if self._retry_timer.isActive():
            return
        self._set_state("retrying", f"{reason} - coba lagi dalam {RETRY_MS // 1000} detik")
        self._retry_timer.start()

    # ------------------------------------------------------------ data
    def _on_ready_read(self) -> None:
        self._drain()

    def _drain(self) -> None:
        if not self._socket.bytesAvailable():
            return
        self._buffer += bytes(self._socket.readAll())
        parts = _SPLIT.split(self._buffer)
        self._buffer = parts.pop()          # unfinished message (no terminator yet)
        for part in parts:
            self._deliver(part)
        if len(self._buffer) > MAX_PENDING:
            self._flush_pending()
        if self._buffer:
            self._idle_timer.start()
        else:
            self._idle_timer.stop()

    def _flush_pending(self, deliver: bool = True) -> None:
        pending, self._buffer = self._buffer, b""
        if pending and deliver:
            self._deliver(pending)

    def _deliver(self, raw: bytes) -> None:
        text = decode(raw)
        if text:
            self.dataReceived.emit(text)

    def _set_state(self, state: str, message: str) -> None:
        self.state = state
        self.message = message
        self.statusChanged.emit(state, message)
