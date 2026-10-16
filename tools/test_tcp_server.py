"""Server TCP uji untuk menu Kolektor (pengganti alat/scanner yang mengirim data lewat IP).

Contoh:
    python tools/test_tcp_server.py --port 9004

Lalu di aplikasi, menu Kolektor: IP Server = IP komputer ini (atau 127.0.0.1), Port = 9004,
klik Start. Setiap aplikasi tersambung, server ini mengirim satu data per --interval detik
(diakhiri CR LF). Setiap data ke-4 sengaja diulang supaya terlihat duplikat diabaikan.
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
    sent = []
    try:
        for i in range(1, count + 1):
            if i % 4 == 0 and sent:
                data = sent[-1]                       # duplikat
            else:
                data = f"https&&&aslibos.com&scan&BX{i:05d}{datetime.now():%Y_%m_%d_%H_%M_%S}.jpg"
                sent.append(data)
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
