"""Kirim foto uji ke FTP Photo Renamer (tanpa kamera).

Contoh:
    python tools/test_upload.py --host 127.0.0.1 --port 21 --user admin --password admin

Mengirim 5 file:
  1. 3975 264 812_<sekarang>.jpg                                  -> disimpan
  2. 3975 264 812_<sekarang+5 detik>.jpg                          -> duplikat (code sama)
  3. https&&&aslibos.com&scan&BXXAXESPP<sekarang>.jpg             -> disimpan, code BXXAXESPP
  4. https&&&aslibos.com&scan&BXXAXESPP<sekarang+1 detik>.jpg     -> duplikat
  5. snapshot.jpg                                                 -> format tidak sesuai (hanya dicatat di log)
"""
from __future__ import annotations

import argparse
import ftplib
import io
import os
from datetime import datetime, timedelta


def fake_jpeg() -> bytes:
    return b"\xff\xd8\xff\xe0" + os.urandom(20_000) + b"\xff\xd9"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=21)
    parser.add_argument("--user", default="admin")
    parser.add_argument("--password", default="admin")
    parser.add_argument("--active", action="store_true", help="pakai mode aktif (PORT) bukan pasif")
    args = parser.parse_args()

    now = datetime.now()
    names = [
        f"3975 264 812_{now:%Y_%m_%d_%H_%M_%S}.jpg",
        f"3975 264 812_{now + timedelta(seconds=5):%Y_%m_%d_%H_%M_%S}.jpg",
        f"https&&&aslibos.com&scan&BXXAXESPP{now:%Y_%m_%d_%H_%M_%S}.jpg",
        f"https&&&aslibos.com&scan&BXXAXESPP{now + timedelta(seconds=1):%Y_%m_%d_%H_%M_%S}.jpg",
        "snapshot.jpg",
    ]

    ftp = ftplib.FTP()
    ftp.connect(args.host, args.port, timeout=15)
    print(ftp.getwelcome())
    ftp.login(args.user, args.password)
    ftp.set_pasv(not args.active)
    for name in names:
        reply = ftp.storbinary("STOR " + name, io.BytesIO(fake_jpeg()))
        print(f"{name:60s} {reply}")
    ftp.quit()
    print("Selesai. Lihat tab 'File diterima' di aplikasi.")


if __name__ == "__main__":
    main()
