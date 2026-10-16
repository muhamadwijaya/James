"""FRT Cam license tool - for the VENDOR (you), not for customers.

  python tools/license_tool.py keygen [--write]
      Create your own key pair. The private seed goes to tools/vendor_keys/private_seed.hex
      (keep it secret, never ship it). --write also puts the public key into gui/activation.py;
      rebuild the .exe afterwards.

  python tools/license_tool.py hwid
      Print the HWID of the machine you run it on (handy for testing).

  python tools/license_tool.py issue --hwid <HWID> [--name "PT Contoh"] [--days 365] [--otp 123456] [--out kode.lic]
      Issue an activation code + OTP for one customer PC. The customer sends you the HWID shown
      in the activation window; you send back the CODE and OTP (e.g. via WhatsApp/SMS from your
      phone). --days 0 = never expires. --out writes a .lic file the customer can load.

Until you run keygen, a built-in DEMO key is used. Anyone with this repository can issue
codes for the demo key, so generate your own pair before giving the app to customers.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import secrets
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gui"))
sys.setrecursionlimit(5000)

import activation  # noqa: E402
import ed25519  # noqa: E402
import hwid as hwid_mod  # noqa: E402

KEY_DIR = Path(__file__).resolve().parent / "vendor_keys"
PRIVATE_FILE = KEY_DIR / "private_seed.hex"
DEMO_PHRASE = b"FRT Cam DEMO vendor key v2 - regenerate with: python tools/license_tool.py keygen"


def _load_seed() -> tuple[bytes, bool]:
    """(seed, is_demo)."""
    if PRIVATE_FILE.exists():
        seed = bytes.fromhex(PRIVATE_FILE.read_text(encoding="ascii").strip())
        return seed, False
    return hashlib.sha256(DEMO_PHRASE).digest(), True


def cmd_keygen(write: bool) -> None:
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    if PRIVATE_FILE.exists():
        print(f"Sudah ada kunci di {PRIVATE_FILE}. Hapus dulu jika memang ingin membuat ulang.")
        print("(Membuat ulang = semua kode aktivasi lama tidak berlaku.)")
        return
    seed = secrets.token_bytes(32)
    PRIVATE_FILE.write_text(seed.hex(), encoding="ascii")
    pub = ed25519.publickey(seed).hex()
    print(f"Kunci privat disimpan : {PRIVATE_FILE}  (RAHASIA - jangan dibagikan / jangan di-commit)")
    print(f"Kunci publik          : {pub}")
    if write:
        path = ROOT / "gui" / "activation.py"
        text = path.read_text(encoding="utf-8")
        new = re.sub(r'VENDOR_PUBLIC_KEY_HEX = "[0-9a-f]{64}"', f'VENDOR_PUBLIC_KEY_HEX = "{pub}"', text)
        path.write_text(new, encoding="utf-8")
        print(f"gui/activation.py sudah diperbarui. Build ulang aplikasi (build.bat).")
    else:
        print('Tempel ke gui/activation.py:  VENDOR_PUBLIC_KEY_HEX = "' + pub + '"  lalu build ulang.')


def cmd_issue(hwid_value: str, name: str, days: int, otp: str | None, out: str | None) -> None:
    hwid_value = hwid_value.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", hwid_value):
        sys.exit("HWID harus 64 karakter hex (salin lengkap dari jendela aktivasi).")
    seed, demo = _load_seed()
    if demo:
        print("PERINGATAN: memakai kunci DEMO. Jalankan 'keygen' untuk kunci Anda sendiri.\n")
    pub_hex = ed25519.publickey(seed).hex()
    if pub_hex != activation.VENDOR_PUBLIC_KEY_HEX:
        print("PERINGATAN: kunci publik di gui/activation.py BEDA dengan kunci privat ini.")
        print("            Kode ini tidak akan diterima oleh aplikasi sampai keduanya cocok.\n")
    otp = otp or f"{secrets.randbelow(1_000_000):06d}"
    if not re.fullmatch(r"\d{6}", otp):
        sys.exit("OTP harus 6 angka.")
    expiry = 0 if days <= 0 else activation.days_from_date(date.today() + timedelta(days=days))
    code = activation.sign_payload(seed, hwid_value, name, expiry, otp)
    # self-check with the same verifier the app uses
    assert activation.verify(code, otp, hwid_value, pub_hex) is not None
    print(f"HWID : {hwid_value}")
    print(f"Nama : {name or '-'}")
    print(f"Masa : {'selamanya' if expiry == 0 else 's/d ' + str(date.today() + timedelta(days=days))}")
    print()
    print("KODE AKTIVASI:")
    print(code)
    print()
    print(f"OTP  : {otp}")
    if out:
        activation.write_lic_file(out, hwid_value, code, otp, name)
        print(f"\nFile lisensi ditulis: {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="FRT Cam license tool (vendor)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    k = sub.add_parser("keygen", help="buat pasangan kunci vendor")
    k.add_argument("--write", action="store_true", help="tulis kunci publik ke gui/activation.py")
    sub.add_parser("hwid", help="tampilkan HWID komputer ini")
    i = sub.add_parser("issue", help="buat kode aktivasi + OTP untuk satu HWID")
    i.add_argument("--hwid", required=True)
    i.add_argument("--name", default="")
    i.add_argument("--days", type=int, default=0, help="0 = selamanya")
    i.add_argument("--otp", default=None, help="6 angka (default: acak)")
    i.add_argument("--out", default=None, help="tulis file .lic")
    args = parser.parse_args()

    if args.cmd == "keygen":
        cmd_keygen(args.write)
    elif args.cmd == "hwid":
        print(hwid_mod.hwid())
    elif args.cmd == "issue":
        cmd_issue(args.hwid, args.name, args.days, args.otp, args.out)


if __name__ == "__main__":
    main()
