"""Kolektor: collect data received over FTP into a locked batch CSV (Alb-NNNNNN).

A session is started with a batch name (e.g. Alb-000123) and a target folder. From Start
until Done, every received item - and any link/string added by hand - is appended to one
CSV file locked to that batch. Duplicates (same code, or the same link string) are ignored.
"""
from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

import naming

BATCH_PREFIX = "Alb-"
BATCH_RE = re.compile(r"^Alb-\d{4,}$")
CSV_DELIMITER = ";"          # Indonesian Excel opens semicolon CSV without "Text to Columns"
CSV_HEADER = ["No", "Batch", "Waktu diterima", "Waktu foto", "Code", "Link/String asli",
              "Nama baru", "Status", "Dari", "Ukuran (bytes)"]
STATUS_LABEL = {"saved": "Disimpan", "duplicate": "Duplikat", "unmatched": "Tidak sesuai",
                "error": "Gagal", "manual": "Manual"}


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
        self._seen: set[str] = set()
        self._file = None
        self._writer = None

    # --------------------------------------------------------------- lifecycle
    def start(self, number: str, folder: str) -> Path:
        """Open (or continue) the batch CSV and lock the session to it."""
        if self.active:
            raise RuntimeError("Sesi kolektor sudah berjalan")
        batch = batch_name(number)
        directory = Path(folder)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{batch}.csv"

        self.rows = []
        self.duplicates = 0
        self._seen = set()
        existing = _load_existing(path)       # continue a batch without re-adding its rows
        for row in existing:
            self.rows.append(row)
            self._seen.add(row["_key"])

        self._file = open(path, "a", encoding="utf-8-sig", newline="")
        self._writer = csv.writer(self._file, delimiter=CSV_DELIMITER)
        if not existing and self._file.tell() == 0:
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
    def add_event(self, event: dict) -> CollectResult:
        """Collect a received-file event from the backend (only while active)."""
        if not self.active:
            return CollectResult("ignored")
        link = event.get("original") or ""
        code = event.get("code") or ""
        if not code:
            parsed = naming.parse(link)
            code = parsed[0] if parsed else ""
        photo_time = _photo_time(link)
        return self._add(received=event.get("time") or _now(), photo_time=photo_time, code=code,
                         link=link, new_name=event.get("name") or "", status=event.get("status") or "",
                         client=event.get("client") or "", size=event.get("bytes"))

    def add_link(self, text: str) -> CollectResult:
        """Collect a link/string typed or pasted by the user."""
        if not self.active:
            return CollectResult("ignored")
        link = (text or "").strip()
        if not link:
            return CollectResult("ignored")
        parsed = naming.parse(link)
        code = parsed[0] if parsed else ""
        return self._add(received=_now(), photo_time=_photo_time(link), code=code, link=link,
                         new_name="", status="manual", client="manual", size=None)

    def _add(self, received, photo_time, code, link, new_name, status, client, size) -> CollectResult:
        key = ("code:" + code.lower()) if code else ("link:" + link.strip().lower())
        if key in self._seen:
            self.duplicates += 1
            return CollectResult("duplicate")
        self._seen.add(key)
        row = {
            "_key": key,
            "no": len(self.rows) + 1,
            "batch": self.batch,
            "received": received,
            "photo_time": photo_time,
            "code": code,
            "link": link,
            "name": new_name,
            "status": status,
            "client": client,
            "size": "" if size in (None, "") else int(size),
        }
        self.rows.append(row)
        if self._writer is not None:
            self._writer.writerow([row["no"], row["batch"], row["received"], row["photo_time"], row["code"],
                                   row["link"], row["name"], STATUS_LABEL.get(status, status), row["client"],
                                   row["size"]])
            self._file.flush()
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
                writer.writerow([row["no"], row["batch"], row["received"], row["photo_time"], row["code"],
                                 row["link"], row["name"], STATUS_LABEL.get(row["status"], row["status"]),
                                 row["client"], row["size"]])
        return path


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _photo_time(link: str) -> str:
    parsed = naming.parse(link)
    return parsed[1].strftime("%Y-%m-%d %H:%M:%S") if parsed else ""


def _load_existing(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f, delimiter=CSV_DELIMITER)
            header = next(reader, None)
            if header != CSV_HEADER:
                return []   # unknown layout: start fresh rather than corrupt it
            for values in reader:
                if len(values) < len(CSV_HEADER):
                    continue
                code, link = values[4], values[5]
                key = ("code:" + code.lower()) if code else ("link:" + link.strip().lower())
                rows.append({"_key": key, "no": len(rows) + 1, "batch": values[1], "received": values[2],
                             "photo_time": values[3], "code": code, "link": link, "name": values[6],
                             "status": values[7], "client": values[8], "size": values[9]})
    except (OSError, ValueError, StopIteration):
        return rows
    return rows
