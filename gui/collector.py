"""Kolektor: collect data received over TCP/IP into one locked batch CSV (Alb-NNNNNN).

The CSV has exactly two columns: the data (a link) and the timestamp it arrived.
A session is started with a batch name (e.g. Alb-000123) and a folder; from Start until
Done every new piece of data is appended (flushed each time).

One received message may hold several links separated by ";" - each link becomes its own
row, in the order received:
    https://aslibos.com/scan/A;https://aslibos.com/scan/B  ->  row A, then row B below it
    https://aslibos.com/scan/A;https://aslibos.com/scan/A  ->  row A only
Data that is already in the batch is a duplicate and is ignored.
"""
from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

BATCH_PREFIX = "Alb-"
BATCH_RE = re.compile(r"^Alb-\d{4,}$")
CSV_DELIMITER = ";"          # Indonesian Excel opens semicolon CSV without "Text to Columns"
CSV_HEADER = ["Data", "Timestamp"]
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
DATA_SEPARATOR = ";"         # several links in one message: link1;link2;...


def split_data(message: str) -> list[str]:
    """'link1;link2' -> ['link1', 'link2'] (blank parts dropped, order kept)."""
    return [part.strip() for part in (message or "").split(DATA_SEPARATOR) if part.strip()]


def batch_name(number: str) -> str:
    digits = "".join(c for c in str(number) if c.isdigit()) or "0"
    return BATCH_PREFIX + digits.zfill(6)


def default_number(previous: str) -> str:
    """Next batch number after the previous one (Alb-000123 -> 000124)."""
    digits = "".join(c for c in (previous or "") if c.isdigit())
    if not digits:
        return "000001"
    width = max(6, len(digits))
    return str(int(digits) + 1).zfill(width)


class CollectResult:
    __slots__ = ("outcome", "row")

    def __init__(self, outcome: str, row: dict | None = None) -> None:
        self.outcome = outcome          # "added" | "duplicate" | "ignored"
        self.row = row


class Collector:
    """One collection session. Rows are appended to the CSV as they arrive (flushed each time)."""

    def __init__(self) -> None:
        self.active = False
        self.batch = ""
        self.csv_path: Path | None = None
        self.rows: list[dict] = []
        self.duplicates = 0
        self.write_error = ""
        self._seen: set[str] = set()
        self._file = None
        self._writer = None

    # --------------------------------------------------------------- lifecycle
    def start(self, number: str, folder: str) -> Path:
        """Open (or continue) the batch CSV and lock the session to it.

        Raises OSError if the file cannot be opened, ValueError if a file with that name
        already exists with other columns (it is never overwritten).
        """
        if self.active:
            raise RuntimeError("Sesi kolektor sudah berjalan")
        batch = batch_name(number)
        directory = Path(folder)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{batch}.csv"

        existing = _load_existing(path)       # continue a batch without re-adding its rows
        self.rows = []
        self.duplicates = 0
        self.write_error = ""
        self._seen = set()
        for data, stamp in existing:
            if data not in self._seen:
                self._seen.add(data)
                self._seen.update(split_data(data))
                self.rows.append({"no": len(self.rows) + 1, "data": data, "timestamp": stamp})

        self._file = open(path, "a", encoding="utf-8-sig", newline="")
        self._writer = csv.writer(self._file, delimiter=CSV_DELIMITER)
        if self._file.tell() == 0:
            self._writer.writerow(CSV_HEADER)
            self._file.flush()

        self.active = True
        self.batch = batch
        self.csv_path = path
        return path

    def done(self) -> None:
        self._close()
        self.active = False

    def reset(self) -> None:
        """Clear the on-screen collection (the CSV on disk is kept)."""
        self._close()
        self.active = False
        self.batch = ""
        self.csv_path = None
        self.rows = []
        self.duplicates = 0
        self.write_error = ""
        self._seen = set()

    def _close(self) -> None:
        if self._file is not None:
            try:
                self._file.close()
            except OSError:
                pass
        self._file = None
        self._writer = None

    # --------------------------------------------------------------- collecting
    def add(self, message: str, timestamp: str | None = None) -> list[CollectResult]:
        """Collect one received message (only while a session is active).

        The message is split on ";" and every part is added as its own row with the same
        timestamp. Parts already collected (earlier, or earlier in this message) are ignored.
        """
        if not self.active:
            return [CollectResult("ignored")]
        parts = split_data(message)
        if not parts:
            return [CollectResult("ignored")]
        stamp = timestamp or _now()
        return [self._add_one(part, stamp) for part in parts]

    def _add_one(self, text: str, timestamp: str) -> CollectResult:
        if text in self._seen:
            self.duplicates += 1
            return CollectResult("duplicate")
        self._seen.add(text)
        row = {"no": len(self.rows) + 1, "data": text, "timestamp": timestamp}
        self.rows.append(row)
        if self._writer is not None:
            try:
                self._writer.writerow([row["data"], row["timestamp"]])
                self._file.flush()
                self.write_error = ""
            except OSError as exc:
                self.write_error = str(exc)
        return CollectResult("added", row)

    # --------------------------------------------------------------- export
    def export(self, dest: str) -> Path:
        """Write the whole current collection to a new CSV (snapshot)."""
        path = Path(dest)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter=CSV_DELIMITER)
            writer.writerow(CSV_HEADER)
            for row in self.rows:
                writer.writerow([row["data"], row["timestamp"]])
        return path


def _now() -> str:
    return datetime.now().strftime(TIME_FORMAT)


def _load_existing(path: Path) -> list[tuple[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=CSV_DELIMITER)
        header = next(reader, None)
        if header is None:
            return []
        if header != CSV_HEADER:
            raise ValueError(f"File {path.name} sudah ada dengan kolom yang berbeda.\n"
                             "Pakai nomor batch lain agar file lama tidak tercampur.")
        rows = []
        for values in reader:
            data = values[0].strip() if values else ""
            if data:
                rows.append((data, values[1] if len(values) > 1 else ""))
    return rows
