# FTP Photo Renamer

Aplikasi Windows untuk **menerima foto dari kamera via FTP**, lalu otomatis **me-rename** dan
menyimpannya ke folder tujuan.

- GUI: **Python + PySide6**
- Backend FTP server: **C#** (async, setiap koneksi kamera diproses paralel)
- Build langsung jadi **1 file `.exe`** dengan `build.bat`

## Format nama file

| | Format | Contoh |
|---|---|---|
| Diterima dari FTP | `CODE_YYYY_MM_DD_HH_MM_SS.jpg` | `3975 264 812_2026_10_10_00_08_46.jpg` |
| Disimpan ke folder | `LINE-ID_YYYYMMDD_HHMMSS_CODE.jpg` | `00001_20261010_000846_3975264812.jpg` |

- Spasi di CODE dihapus (`3975 264 812` → `3975264812`).
- LINE-ID diisi di aplikasi dan bisa diganti saat server berjalan.
- Kolom **Uji nama file** di aplikasi menampilkan hasil rename sebelum server dijalankan.

## Fitur

- IP dan port FTP bisa diatur (0.0.0.0 = semua kartu jaringan), plus username/password
  (atau terima login apa saja).
- Mode pasif (PASV/EPSV) dan aktif (PORT/EPRT), rentang port pasif bisa diatur.
- **Anti duplikat**: jika CODE yang sama dikirim lagi, hanya 1 file yang disimpan.
  - Rentang cek duplikat: *Selamanya* (default) atau N menit.
  - Code yang sudah ada di folder tujuan ikut dihitung (tetap berlaku setelah aplikasi ditutup/dibuka lagi).
  - Opsional: simpan duplikat ke subfolder `_duplikat` (default: dibuang).
- Tombol **Browse** untuk memilih folder tujuan, dan **Buka** untuk membuka folder.
- Tabel file diterima (klik dua kali untuk membuka foto), statistik, dan log.
- Pengaturan tersimpan otomatis di `config.json`, dengan opsi *Mulai otomatis saat aplikasi dibuka*.

Folder khusus di dalam folder tujuan:

| Folder | Isi |
|---|---|
| `_tidak_sesuai` | file yang namanya tidak sesuai format (nama asli dipertahankan) |
| `_duplikat` | duplikat, hanya jika opsinya dicentang |
| `.incoming` | file yang sedang diterima (sementara) |

## Build `.exe`

Kebutuhan (Windows 10/11):

1. **Python 3.9+** dari [python.org](https://www.python.org/downloads/). Centang *Add python.exe to PATH*.
2. Backend C# dikompilasi otomatis:
   - jika **.NET SDK 8+** terpasang → `dotnet publish` (self-contained, tidak butuh runtime di PC tujuan);
   - jika tidak → memakai `csc.exe` bawaan Windows (.NET Framework 4.x), **tanpa install apa pun**.

Lalu klik dua kali **`build.bat`**. Hasilnya:

```
dist\FtpPhotoRenamer.exe
```

File `.exe` ini sudah berisi GUI dan backend, jadi cukup salin satu file ini ke PC lain.

## Cara pakai

1. Jalankan `FtpPhotoRenamer.exe`.
2. Isi **IP Address**, **Port** (default 21), **Username**, **Password**.
3. Isi **LINE-ID** (mis. `00001`) dan pilih **Folder tujuan** dengan tombol *Browse...*.
4. Klik **Mulai Server**. Saat pertama kali jalan, izinkan akses di jendela *Windows Firewall*.
5. Di setting FTP kamera, isi IP komputer ini, port, username dan password yang sama.

### Uji tanpa kamera

```
.venv\Scripts\python tools\test_upload.py --host 127.0.0.1 --port 21 --user admin --password admin
```

Script ini mengirim 4 file: 2 tersimpan, 1 duplikat, 1 format tidak sesuai.

## Struktur proyek

```
backend/        FTP server C# (FtpBackend.exe)
  Program.cs          argumen & perintah dari GUI (stdin)
  FtpServer.cs        listener + sesi paralel
  FtpSession.cs       protokol FTP per koneksi
  PhotoProcessor.cs   rename + anti duplikat
  EventSink.cs        event JSON ke GUI (stdout)
gui/            GUI PySide6
  main.py             entry point
  main_window.py      jendela utama
  backend_client.py   menjalankan backend (QProcess)
  naming.py           preview aturan rename
  app_config.py       simpan/muat config.json
tools/test_upload.py  kirim foto uji
build.bat             build semua menjadi dist\FtpPhotoRenamer.exe
```

GUI menjalankan `FtpBackend.exe` sebagai proses terpisah. Backend mengirim event JSON per baris
(stdout), dan GUI mengirim perintah `STOP` / `SET LINEID <id>` lewat stdin. Backend juga bisa
dijalankan sendiri dari command prompt (`FtpBackend.exe --help`).
