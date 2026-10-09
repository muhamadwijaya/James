"""Antarmuka baris perintah untuk pm3tool.

Contoh:
    python -m pm3tool scan
    python -m pm3tool read-hf
    python -m pm3tool read-lf
    python -m pm3tool recover-keys --dict my_keys.dic
    python -m pm3tool dump --keyfile hf-mf-ABCD1234-key.bin
"""

from __future__ import annotations

import argparse
import os
import sys

from .client import PM3Client, PM3NotFound
from . import scanner


def _print_identity(title: str, ident: dict) -> None:
    print(f"\n=== {title} ===")
    for field in ("uid", "atqa", "sak", "id"):
        if field in ident and ident[field]:
            print(f"  {field.upper():5}: {ident[field]}")


def _make_client(args: argparse.Namespace) -> PM3Client:
    return PM3Client(binary=args.binary, port=args.port, timeout=args.timeout)


def cmd_check(args) -> int:
    res = scanner.check_device(_make_client(args))
    print(res.stdout or res.stderr)
    return 0 if res.ok else 1


def cmd_scan(args) -> int:
    data = scanner.scan_auto(_make_client(args))
    _print_identity("HF (13.56 MHz)", data["hf"])
    if data["lf_em410x"]:
        print("\n=== LF (125 kHz) ===")
        print(f"  EM410x ID: {data['lf_em410x']}")
    if args.raw:
        print("\n--- RAW HF ---\n" + data["hf_raw"])
        print("\n--- RAW LF ---\n" + data["lf_raw"])
    return 0


def cmd_read_hf(args) -> int:
    data = scanner.read_hf_14a(_make_client(args))
    _print_identity("ISO14443-A", data)
    if args.raw:
        print("\n" + data["raw"])
    return 0


def cmd_read_lf(args) -> int:
    data = scanner.read_lf_em410x(_make_client(args))
    if data["id"]:
        print(f"EM410x ID: {data['id']}")
    else:
        print("Tidak ada kartu LF terdeteksi.")
        if args.raw:
            print(data["raw"])
    return 0


def cmd_recover(args) -> int:
    print("Menjalankan hf mf autopwn — ini bisa memakan waktu "
          "(hardnested bisa beberapa menit). Jangan lepas kartu dari antena.\n")
    data = scanner.recover_mifare_keys(
        _make_client(args), dictionary=args.dict, timeout=args.timeout
    )
    if data["keys"]:
        print("Key yang ditemukan:")
        print(f"  {'Sektor':>6} | Tipe | Key")
        for k in data["keys"]:
            print(f"  {k['sector']:>6} |  {k['type']}   | {k['key']}")
    else:
        print("Belum ada key yang berhasil dipulihkan.")
    if args.raw or not data["keys"]:
        print("\n--- RAW ---\n" + data["raw"])
    return 0 if data["ok"] else 1


def cmd_dump(args) -> int:
    res = scanner.dump_mifare(_make_client(args), keyfile=args.keyfile)
    print(res.stdout or res.stderr)
    return 0 if res.ok else 1


def cmd_view(args) -> int:
    from . import dumpview
    try:
        print(dumpview.view_file(args.dump, sectors_arg=args.sectors,
                                 mode=args.format))
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_recover_reader(args) -> int:
    from . import attack
    print("PM3 menyamar sebagai kartu. Tempelkan PM3 ke reader Anda "
          "berulang sampai key muncul. Tekan tombol PM3 untuk berhenti.\n")
    data = attack.recover_via_reader(_make_client(args), uid=args.uid,
                                     timeout=args.timeout)
    if data["keys"]:
        print("Key ditemukan:")
        for k in data["keys"]:
            print(f"  {k}")
    else:
        print("Belum ada key terpulihkan.")
    if args.raw or not data["keys"]:
        print("\n--- RAW ---\n" + data["raw"])
    return 0 if data["ok"] else 1


def cmd_sniff(args) -> int:
    from . import attack
    print("Menyadap reader<->kartu. Tap kartu ke reader, lalu tekan tombol "
          "PM3 untuk mengakhiri sniff.\n")
    data = attack.sniff_and_crack(_make_client(args), sniff_timeout=args.timeout)
    if data["keys"]:
        print("Key ditemukan:")
        for k in data["keys"]:
            print(f"  {k}")
    else:
        print("Belum ada key terpulihkan dari trace.")
    if args.raw or not data["keys"]:
        print("\n--- TRACE ---\n" + data["raw"])
    return 0 if data["ok"] else 1


def cmd_clone(args) -> int:
    from . import clone
    client = _make_client(args)
    if args.info:
        data = clone.card_info(client)
        print("MAGIC:" , ", ".join(data["generations"]) if data["magic"] else "bukan/none")
        print(data["raw"])
        return 0
    if args.set_uid:
        res = clone.set_magic_uid(client, args.set_uid)
        print(res.stdout or res.stderr)
        return 0 if res.ok else 1
    if args.gen1a:
        if not args.dump:
            print("ERROR: --dump wajib untuk --gen1a", file=sys.stderr)
            return 2
        res = clone.clone_to_gen1a(client, args.dump)
        print(res.stdout or res.stderr)
        return 0 if res.ok else 1
    # default: restore pakai key
    res = clone.restore_dump(client, dumpfile=args.dump, keyfile=args.keyfile,
                             write_block0=args.block0)
    print(res.stdout or res.stderr)
    return 0 if res.ok else 1


def cmd_gui(args) -> int:
    # Utamakan GUI PySide6; fallback ke Tkinter bila PySide6 tak terpasang.
    try:
        from .gui_qt import main as gui_main
    except ImportError:
        try:
            from .gui import main as gui_main
        except ImportError as exc:
            print("ERROR: tidak ada GUI toolkit. Install PySide6 "
                  f"(pip install PySide6) atau tkinter. Detail: {exc}",
                  file=sys.stderr)
            return 2
        print("PySide6 tidak ada, memakai GUI Tkinter.", file=sys.stderr)
    return gui_main()


def cmd_gui_tk(args) -> int:
    try:
        from .gui import main as gui_main
    except ImportError as exc:
        print(f"ERROR: tidak bisa memuat GUI Tkinter: {exc}", file=sys.stderr)
        return 2
    return gui_main()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pm3tool",
        description="Wrapper Proxmark3 untuk membaca RFID, menampilkan "
                    "data, dan memulihkan key MIFARE pada kartu sendiri.",
    )
    p.add_argument("--binary", default=os.environ.get("PM3_BINARY", "pm3"),
                   help="Executable client PM3 (atau set env PM3_BINARY).")
    p.add_argument("--port", default=os.environ.get("PM3_PORT"),
                   help="Port serial, mis. COM10 (atau set env PM3_PORT).")
    p.add_argument("--timeout", type=float, default=30.0,
                   help="Timeout per perintah (detik).")
    p.add_argument("--raw", action="store_true",
                   help="Tampilkan juga output mentah PM3.")

    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="Cek koneksi & tuning antena.").set_defaults(func=cmd_check)
    sub.add_parser("scan", help="Deteksi otomatis LF + HF.").set_defaults(func=cmd_scan)
    sub.add_parser("read-hf", help="Baca kartu 13.56 MHz.").set_defaults(func=cmd_read_hf)
    sub.add_parser("read-lf", help="Baca kartu 125 kHz EM410x.").set_defaults(func=cmd_read_lf)

    rec = sub.add_parser("recover-keys",
                         help="Pulihkan key MIFARE Classic (autopwn).")
    rec.add_argument("--dict", default=None, help="File dictionary key opsional.")
    rec.set_defaults(func=cmd_recover, timeout=600.0)

    dmp = sub.add_parser("dump", help="Dump isi MIFARE memakai key diketahui.")
    dmp.add_argument("--keyfile", default=None, help="File .bin key dari autopwn.")
    dmp.set_defaults(func=cmd_dump)

    vw = sub.add_parser("view", help="Lihat isi dump (hex/ASCII).")
    vw.add_argument("--dump", required=True, help="File dump (.bin/.eml/.json).")
    vw.add_argument("--sectors", default=None,
                    help="Filter sektor, mis. '1-4' atau '1,3,5' (default: semua).")
    vw.add_argument("--format", choices=["hex", "ascii", "both"], default="both",
                    help="Format tampilan (default: both).")
    vw.set_defaults(func=cmd_view)

    rr = sub.add_parser("recover-reader",
                        help="Pulihkan key lewat reader (mfkey32, sim).")
    rr.add_argument("--uid", default=None, help="UID yang disimulasikan (hex).")
    rr.set_defaults(func=cmd_recover_reader, timeout=240.0)

    sn = sub.add_parser("sniff", help="Sniff reader↔kartu lalu crack (trace).")
    sn.set_defaults(func=cmd_sniff, timeout=240.0)

    cl = sub.add_parser("clone", help="Clone/pindah data ke chip baru.")
    cl.add_argument("--info", action="store_true", help="Deteksi kartu magic.")
    cl.add_argument("--gen1a", action="store_true",
                    help="Tulis seluruh dump+UID ke magic Gen1a (hf mf cload).")
    cl.add_argument("--dump", default=None, help="File dump sumber (.bin/.eml/.json).")
    cl.add_argument("--keyfile", default=None, help="File key untuk restore.")
    cl.add_argument("--block0", action="store_true",
                    help="Ikut tulis blok 0/UID saat restore (Gen2/CUID).")
    cl.add_argument("--set-uid", default=None, help="Set UID magic Gen1a (hex).")
    cl.set_defaults(func=cmd_clone)

    sub.add_parser("gui", help="Buka GUI (PySide6, fallback Tkinter).").set_defaults(func=cmd_gui)
    sub.add_parser("gui-tk", help="Buka GUI Tkinter.").set_defaults(func=cmd_gui_tk)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # recover-keys punya timeout default sendiri (600s) lewat set_defaults,
    # tapi flag global --timeout tetap bisa menimpanya bila diberikan.
    try:
        return args.func(args)
    except PM3NotFound as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nDibatalkan.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
