"""Server TCP uji untuk menu Kolektor (pengganti alat/scanner yang mengirim data lewat IP).

Contoh:
    python tools/test_tcp_server.py --port 9004

Lalu di aplikasi, menu Kolektor: IP Server = IP komputer ini (atau 127.0.0.1), Port = 9004,
klik Start. Setiap aplikasi tersambung, server ini mengirim satu pesan per --interval detik
(diakhiri CR LF), bergiliran:
  https://aslibos.com/scan/BX00001                                -> 1 baris
  https://aslibos.com/scan/BX00002;https://aslibos.com/scan/BX00002 -> 1 baris (sama, yg kedua dibuang)
  https://aslibos.com/scan/BX00003;https://aslibos.com/scan/BX00004 -> 2 baris (BX00004 di bawahnya)
  https://aslibos.com/scan/BX00001                                -> duplikat, diabaikan
Tekan Ctrl+C untuk berhenti.
"""
from __future__ import annotations

import argparse
import socket
import threading
import time
from datetime import datetime


def serve_client(conn: socket.socket, addr, interval: float, count: int) -> None:
    print(f"[{datetime.now():%H:%M:%S}] tersambung: {addr[0]}:{addr[1]}")
    link = lambda n: f"https://aslibos.com/scan/BX{n:05d}"
    n = 0
    try:
        for i in range(count):
            kind = i % 4
            if kind == 0:
                n += 1
                data = link(n)
            elif kind == 1:
                n += 1
                data = f"{link(n)};{link(n)}"               # 2x sama -> 1 baris
            elif kind == 2:
                data = f"{link(n + 1)};{link(n + 2)}"       # 2 link beda -> 2 baris
                n += 2
            else:
                data = link(n - 3)                          # sudah pernah -> duplikat
            conn.sendall(data.encode("utf-8") + b"\r\n")
            print(f"  kirim: {data}")
            time.sleep(interval)
    except OSError as exc:
        print(f"  koneksi {addr[0]} putus: {exc}")
    finally:
        conn.close()
        print(f"[{datetime.now():%H:%M:%S}] selesai: {addr[0]}:{addr[1]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ip", default="0.0.0.0", help="IP yang didengarkan (default semua)")
    parser.add_argument("--port", type=int, default=9004)
    parser.add_argument("--interval", type=float, default=1.0, help="jeda antar data (detik)")
    parser.add_argument("--count", type=int, default=20, help="jumlah data per koneksi")
    args = parser.parse_args()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.ip, args.port))
    server.listen(5)
    print(f"Server TCP uji aktif di {args.ip}:{args.port} - menunggu aplikasi tersambung (Ctrl+C untuk berhenti)")
    try:
        while True:
            conn, addr = server.accept()
            threading.Thread(target=serve_client, args=(conn, addr, args.interval, args.count), daemon=True).start()
    except KeyboardInterrupt:
        print("berhenti")
    finally:
        server.close()


if __name__ == "__main__":
    main()
