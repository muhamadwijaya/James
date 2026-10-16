"""Where the activation is stored: Windows registry (HKCU) + a backup file.

Both are written on activation and either is accepted on launch (the file lets the app
work even if the registry is cleared, e.g. by a cleaner). The code is still re-verified
cryptographically against the live HWID, so a copied registry/file is useless on another PC.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_REG_PATH = r"Software\FRT Cam\License"
APP_FOLDER = "FRTCam"


def _file_path() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or str(Path.home())
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_FOLDER / "license.json"


def _reg_save(code: str, otp: str) -> bool:
    try:
        import winreg  # type: ignore
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as key:
            winreg.SetValueEx(key, "Code", 0, winreg.REG_SZ, code)
            winreg.SetValueEx(key, "Otp", 0, winreg.REG_SZ, otp)
        return True
    except Exception:
        return False


def _reg_load() -> dict | None:
    try:
        import winreg  # type: ignore
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_PATH) as key:
            code = winreg.QueryValueEx(key, "Code")[0]
            otp = winreg.QueryValueEx(key, "Otp")[0]
        if code:
            return {"code": code, "otp": otp}
    except Exception:
        return None
    return None


def _reg_clear() -> None:
    try:
        import winreg  # type: ignore
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, _REG_PATH)
    except Exception:
        pass


def save(code: str, otp: str) -> None:
    _reg_save(code, otp)
    try:
        path = _file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"code": code, "otp": otp}), encoding="utf-8")
    except OSError:
        pass


def load() -> dict | None:
    data = _reg_load()
    if data:
        return data
    try:
        raw = json.loads(_file_path().read_text(encoding="utf-8"))
        if isinstance(raw, dict) and raw.get("code"):
            return {"code": raw.get("code", ""), "otp": raw.get("otp", "")}
    except (OSError, ValueError):
        return None
    return None


def clear() -> None:
    _reg_clear()
    try:
        _file_path().unlink()
    except OSError:
        pass
