"""Counters for the dashboard: since start, today, per-second activity and per-minute series."""
from __future__ import annotations

import time
from collections import deque
from datetime import date
from pathlib import Path

KEYS = ("received", "saved", "duplicate", "unmatched", "error")
_TXT_STATUS = {"Disimpan": "saved", "Duplikat": "duplicate", "Tidak sesuai": "unmatched", "Gagal": "error"}
SERIES_MINUTES = 16


class Stats:
    def __init__(self) -> None:
        self.session = {k: 0 for k in KEYS}
        self.today = {k: 0 for k in KEYS}
        self.day = date.today()
        self._activity: deque[float] = deque()                    # timestamps, last 60 s
        self._recent = {k: deque() for k in KEYS}                 # timestamps, last SERIES_MINUTES

    def record(self, event: dict) -> None:
        self.roll_day()
        now = time.time()
        status = event.get("status", "error")
        if event.get("source") in ("upload", "download"):
            self._bump("received", now)
            self._activity.append(now)
        if event.get("previous") == "unmatched":
            for bucket in (self.session, self.today):
                bucket["unmatched"] = max(0, bucket["unmatched"] - 1)
        if status in self.session:
            self._bump(status, now)

    def _bump(self, key: str, now: float) -> None:
        self.session[key] += 1
        self.today[key] += 1
        self._recent[key].append(now)

    def roll_day(self) -> bool:
        """Reset the 'hari ini' counters after midnight. Returns True when the day changed."""
        today = date.today()
        if today != self.day:
            self.day = today
            self.today = {k: 0 for k in KEYS}
            return True
        return False

    def activity(self, seconds: int = 60) -> list[int]:
        now = time.time()
        while self._activity and self._activity[0] < now - seconds:
            self._activity.popleft()
        buckets = [0] * seconds
        for t in self._activity:
            i = seconds - 1 - int(now - t)
            if 0 <= i < seconds:
                buckets[i] += 1
        return buckets

    def series(self, key: str) -> list[int]:
        now = time.time()
        q = self._recent[key]
        while q and q[0] < now - SERIES_MINUTES * 60:
            q.popleft()
        buckets = [0] * SERIES_MINUTES
        for t in q:
            i = SERIES_MINUTES - 1 - int((now - t) // 60)
            if 0 <= i < SERIES_MINUTES:
                buckets[i] += 1
        return buckets

    def load_today(self, target_dir: str) -> None:
        """'Hari ini' counters from today's _log\\diterima_YYYY-MM-DD.txt (survives restarts)."""
        self.day = date.today()
        self.today = {k: 0 for k in KEYS}
        path = Path(target_dir) / "_log" / f"diterima_{self.day.isoformat()}.txt"
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    if line.startswith("#"):
                        continue
                    parts = line.split(" | ", 3)
                    if len(parts) < 3:
                        continue
                    self.today["received"] += 1
                    key = _TXT_STATUS.get(parts[2].strip())
                    if key:
                        self.today[key] += 1
        except OSError:
            pass
