"""Load/save settings as config.json next to the program (falls back to the user profile)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP_NAME = "FtpPhotoRenamer"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _user_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / APP_NAME


DEFAULTS: dict = {
    "ip": "0.0.0.0",
    "port": 21,
    "username": "admin",
    "password": "admin",
    "any_login": False,
    "pasv_min": 50000,
    "pasv_max": 50200,
    "line_id": "00001",
    "target_dir": str(Path.home() / "Pictures" / "FTP_Foto"),
    "dedup": True,
    "dedup_minutes": 0,
    "keep_duplicates": False,
    "autostart": False,
}


def _candidates() -> list[Path]:
    return [app_dir() / "config.json", _user_dir() / "config.json"]


def load() -> dict:
    cfg = dict(DEFAULTS)
    for path in _candidates():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if k in DEFAULTS and type(v) is type(DEFAULTS[k])})
            break
    return cfg


def save(cfg: dict) -> Path | None:
    text = json.dumps(cfg, indent=2, ensure_ascii=False)
    for path in _candidates():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
            return path
        except OSError:
            continue
    return None
