"""License activation for FRT Cam (this app's own protection).

Offline, machine-locked activation ("patch" model):
  * The app computes a Hardware ID (hwid.py) and shows it.
  * The customer requests an Activation Code + OTP from the vendor
    (contact VENDOR_PHONE) - issued with tools/license_tool.py.
  * The code is an Ed25519 signature over (hwid | name | expiry | otp); the app
    verifies it with the embedded vendor PUBLIC key. No secret ships with the app,
    so a code cannot be forged without the vendor private key, and it only works on
    the machine whose HWID it was signed for.
  * On success the activation is stored in the Windows registry AND a file; both are
    re-verified against the live HWID on every launch.

This protects the author's OWN software; it is not a tool to bypass anyone else's.
"""
from __future__ import annotations

import base64
import os
import struct
from dataclasses import dataclass
from datetime import date

import ed25519
import hwid as hwid_mod

# Vendor PUBLIC key (safe to ship). The matching PRIVATE key stays in the license tool.
# This default is the built-in DEMO key - run `python tools/license_tool.py keygen` to
# generate your own pair for production and paste the printed public key here.
VENDOR_PUBLIC_KEY_HEX = "f520160ba8e316c94786466d029b9b706a6c1ecd1d02d40ff01e87d83abe1667"

# Where customers obtain their activation code / OTP (shown in the dialog).
VENDOR_PHONE = "085772869284"

MAGIC = b"FC"
VERSION = 1
EPOCH = date(1970, 1, 1)
_B32_ALPHABET = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")


@dataclass
class LicenseInfo:
    name: str
    expiry_days: int          # 0 = perpetual, else days since 1970-01-01 (last valid day)

    @property
    def perpetual(self) -> bool:
        return self.expiry_days <= 0

    @property
    def expiry_date(self):
        return None if self.perpetual else EPOCH.fromordinal(EPOCH.toordinal() + self.expiry_days)

    def expired(self, today: date | None = None) -> bool:
        if self.perpetual:
            return False
        return (today or date.today()) > self.expiry_date

    def describe(self) -> str:
        who = self.name or "Terdaftar"
        if self.perpetual:
            return f"{who} - selamanya"
        return f"{who} - berlaku s/d {self.expiry_date:%Y-%m-%d}"


def days_from_date(d: date) -> int:
    return d.toordinal() - EPOCH.toordinal()


def _normalize_b32(code: str) -> str:
    text = "".join(c for c in (code or "").upper() if c in _B32_ALPHABET)
    pad = (-len(text)) % 8
    return text + "=" * pad


def encode_code(name: str, expiry_days: int, sig: bytes) -> str:
    name_bytes = (name or "").encode("utf-8")[:60]
    blob = MAGIC + bytes([VERSION]) + struct.pack(">I", max(0, expiry_days)) + bytes([len(name_bytes)]) + name_bytes + sig
    return base64.b32encode(blob).decode("ascii").rstrip("=")


def decode_code(code: str) -> tuple[str, int, bytes] | None:
    try:
        blob = base64.b32decode(_normalize_b32(code))
    except Exception:
        return None
    if len(blob) < 2 + 1 + 4 + 1 or blob[0:2] != MAGIC or blob[2] != VERSION:
        return None
    expiry_days = struct.unpack(">I", blob[3:7])[0]
    name_len = blob[7]
    name_end = 8 + name_len
    sig = blob[name_end:]
    if len(sig) != 64:
        return None
    try:
        name = blob[8:name_end].decode("utf-8")
    except UnicodeDecodeError:
        return None
    return name, expiry_days, sig


def _message(hwid_value: str, name: str, expiry_days: int, otp: str) -> bytes:
    return f"FRTCAM1|{hwid_value}|{name}|{expiry_days}|{otp}".encode("utf-8")


def sign_payload(seed: bytes, hwid_value: str, name: str, expiry_days: int, otp: str) -> str:
    """Vendor side: produce an activation code (needs the private seed)."""
    pub = ed25519.publickey(seed)
    sig = ed25519.signature(_message(hwid_value, name, expiry_days, otp), seed, pub)
    return encode_code(name, expiry_days, sig)


def verify(code: str, otp: str, hwid_value: str | None = None,
           public_key_hex: str | None = None) -> LicenseInfo | None:
    """App side: verify a code+OTP for this machine. Returns LicenseInfo or None."""
    decoded = decode_code(code)
    if decoded is None:
        return None
    name, expiry_days, sig = decoded
    hv = hwid_value or hwid_mod.hwid()
    pub = bytes.fromhex(public_key_hex or VENDOR_PUBLIC_KEY_HEX)
    otp_clean = "".join(c for c in (otp or "") if c.isdigit())
    if not ed25519.verify(sig, _message(hv, name, expiry_days, otp_clean), pub):
        return None
    return LicenseInfo(name=name, expiry_days=expiry_days)


# --------------------------------------------------------------------------- license file
def write_lic_file(path, hwid_value: str, code: str, otp: str, name: str = "") -> None:
    from pathlib import Path
    lines = ["FRT Cam License", f"NAME: {name}", f"HWID: {hwid_value}", f"CODE: {code}", f"OTP: {otp}", ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


def read_lic_file(path) -> dict:
    out: dict = {}
    try:
        from pathlib import Path
        for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                out[key.strip().upper()] = value.strip()
    except OSError:
        return {}
    return {"code": out.get("CODE", ""), "otp": out.get("OTP", ""), "name": out.get("NAME", "")}


# --------------------------------------------------------------------------- high level
def current_license() -> LicenseInfo | None:
    """Verified license for THIS machine, from the env file or the stored activation."""
    env_path = os.environ.get("FRTCAM_LICENSE_FILE")
    if env_path and os.path.isfile(env_path):
        data = read_lic_file(env_path)
        info = verify(data.get("code", ""), data.get("otp", ""))
        if info and not info.expired():
            import license_store
            license_store.save(data.get("code", ""), data.get("otp", ""))   # remember it
            return info
    import license_store
    stored = license_store.load()
    if stored:
        info = verify(stored.get("code", ""), stored.get("otp", ""))
        if info and not info.expired():
            return info
    return None


def is_activated() -> bool:
    return current_license() is not None


def activate(code: str, otp: str) -> tuple[bool, str]:
    """Verify and, on success, store the activation. Returns (ok, message)."""
    info = verify(code, otp)
    if info is None:
        return False, "Kode aktivasi atau OTP salah, atau tidak cocok dengan HWID komputer ini."
    if info.expired():
        return False, f"Lisensi sudah kedaluwarsa ({info.expiry_date:%Y-%m-%d})."
    import license_store
    license_store.save(code.strip(), "".join(c for c in otp if c.isdigit()))
    return True, info.describe()
