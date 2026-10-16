# FRT Cam - System Rename (v2)

Aplikasi Windows untuk **menerima foto via FTP**, lalu otomatis **me-rename** dan
menyimpannya ke folder tujuan.

- GUI: **Python + PySide6**
- Backend: **C#** (async, banyak koneksi diproses paralel)
- Build langsung jadi **1 file `.exe`** dengan `build.bat`

## Baru di versi 2

- **Kolektor (TCP/IP)**: koneksi sendiri, terpisah dari FTP. Aplikasi menjadi **client TCP/IP**:
  isi **IP + Port server** yang mengirim data, lalu setiap link yang diterima
  (mis. `https://aslibos.com/scan/BXXAXESPP`) masuk ke **satu file CSV per batch** dengan
  **2 kolom: Data dan Timestamp**. Beberapa link dalam satu kiriman yang dipisah `;` dijadikan
  **baris sendiri-sendiri**, dan link duplikat **diabaikan**. Alur: isi nama file **Alb-NNNNNN** (angka diisi manual), klik **Start**
  (CSV dikunci + mulai menyambung), klik **Done** bila selesai. Ada tombol **Export CSV**.
  Rename foto tetap lewat **FTP** seperti biasa (tidak tercampur).
- **Aktivasi (model patch)**: aplikasi dikunci per komputer dengan **HWID + registry** dan
  **kode aktivasi** yang ditandatangani (Ed25519), plus **OTP**. Kode dibuat oleh vendor
  (lihat `tools/license_tool.py`) dan diminta ke nomor vendor. Detail di bagian **Aktivasi** di bawah.

## Tampilan

Tema gelap dengan menu samping:

- **Dashboard**:
  - kartu **Koneksi** (mode Server/Client, status "Terhubung") dan **Penamaan & Penyimpanan**
  - tombol **Mulai / Stop** dan grafik **Aktivitas FTP 1 menit terakhir**
  - kartu **Transfer Saat Ini**: nama file, progress, ukuran, kecepatan
  - 6 kartu statistik: Diterima, Disimpan, Duplikat, Tidak sesuai, Gagal, Koneksi aktif.
    Angka besar = sejak aplikasi dibuka, "+N hari ini" = total hari ini.
  - tabel **File Diterima (50 terbaru)**: cari nama file, filter status, Bersihkan,
    Auto-refresh 3 detik (bisa dimatikan), dan tombol mata untuk melihat foto
  - panel **Foto terakhir disimpan**: zoom (atau scroll mouse), layar penuh, foto sebelumnya/berikutnya,
    thumbnail 12 foto terakhir, serta info code, waktu foto, pengirim, waktu diterima, ukuran dan resolusi
- **Log Aktivitas**: 50 baris log terbaru.
- **File Diterima**: tabel yang sama dalam ukuran penuh.
- **Tentang**.

Jendela tanpa bingkai Windows. Geser lewat area judul, klik dua kali untuk maximize, dan ubah ukuran
dari tepi jendela. Opsi *Mulai otomatis saat aplikasi dibuka* ada di tombol roda gigi pada kartu Koneksi.

## Mode koneksi

| Mode | Cara kerja | Dipakai jika |
|---|---|---|
| **Server** | Aplikasi menjadi FTP server. Kamera **mengirim (upload)** foto ke aplikasi. | Kamera bisa di-setting upload FTP ke PC ini |
| **Client** | Aplikasi login ke FTP server lain (NVR / server pusat) dan **mengambil (download)** foto baru secara berkala. | Foto sudah dikumpulkan di FTP server lain |

Aturan rename dan anti duplikat sama untuk kedua mode.

## Format nama file

| Diterima dari FTP | Disimpan ke folder |
|---|---|
| `3975 264 812_2026_10_10_00_08_46.jpg` | `00001_20261010_000846_3975264812.jpg` |
| `https&&&aslibos.com&scan&BXXAXESPP2026_10_14_12_16_53.jpg` | `00001_20261014_121653_BXXAXESPP.jpg` |

Format simpan: `LINE-ID_YYYYMMDD_HHMMSS_CODE.jpg`.

- Aplikasi mencari tanggal-jam `YYYY_MM_DD_HH_MM_SS` (sampai detik) di nama file.
- **CODE** = teks tepat sebelum tanggal, setelah pemisah terakhir (`&` `/` `=` `?` `#` `_` `:` `;`).
  Awalan seperti `https&&&aslibos.com&scan&` diabaikan, panjang CODE bebas, dan CODE boleh
  langsung menempel ke tanggal (`BXXAXESPP2026_...`).
- Spasi di CODE dihapus (`3975 264 812` → `3975264812`).
- LINE-ID diisi di aplikasi dan bisa diganti saat sedang berjalan.
- Kolom **Uji nama file** di aplikasi menampilkan hasil rename sebelum server dijalankan.

## Fitur

**Mode Server**
- IP dan port FTP bisa diatur (0.0.0.0 = semua kartu jaringan), plus username/password
  (atau terima login apa saja).
- Mode pasif (PASV/EPSV) dan aktif (PORT/EPRT), rentang port pasif bisa diatur.

**Mode Client**
- IP/host, port, username, password server FTP, dan folder remote (bisa termasuk subfolder).
- Cek foto baru setiap N detik, download dengan beberapa koneksi paralel (default 3).
- File yang masih ditulis di server diambil setelah ukurannya stabil.
- File yang sudah diambil diingat (`.incoming\remote_<host>_<port>.txt`), jadi tidak diunduh ulang.
- Opsional: hapus file di server setelah berhasil diambil.
- Jika server mati/putus, aplikasi mencoba terhubung lagi otomatis.
- Diambil: `.jpg .jpeg .png .bmp`. Jika beberapa foto dengan code sama ada di server, yang paling lama disimpan.
- Mendukung listing MLSD serta LIST format Unix dan Windows/IIS.

**Umum**
- **Anti duplikat**: jika CODE yang sama dikirim lagi, hanya 1 file yang disimpan.
  - Rentang cek duplikat: *Selamanya* (default) atau N menit.
  - Code yang sudah ada di folder tujuan ikut dihitung (tetap berlaku setelah aplikasi ditutup/dibuka lagi).
  - Opsional: simpan duplikat ke subfolder `_duplikat` (default: dibuang).
- Tombol **Browse** untuk memilih folder tujuan, dan **Buka** untuk membuka folder.
- Panel **Foto terakhir disimpan**: menampilkan foto terbaru yang berhasil disimpan, beserta
  nama file, code, waktu foto, pengirim, ukuran dan resolusi (klik dua kali untuk membuka foto).
- Tabel file diterima dan log di layar hanya menampilkan **50 data terbaru**, supaya aplikasi tetap
  ringan walau berjalan terus-menerus. Data lengkap disimpan ke file txt per hari (lihat di bawah).
- Statistik jumlah diterima / disimpan / duplikat / tidak sesuai / gagal. Angka "hari ini" dibaca
  ulang dari log txt hari ini, jadi tetap benar setelah aplikasi dibuka ulang.
- Pengaturan tersimpan otomatis di `config.json`, dengan opsi *Mulai otomatis saat aplikasi dibuka*.

**File yang formatnya tidak sesuai** (tidak ada tanggal-jam atau CODE kosong) **tidak disimpan**
supaya tidak memakan ruang hardisk. Nama file-nya dicatat di log txt harian:

```
_log\tidak_sesuai_2026-10-14.txt
2026-10-14 12:17:41 | 192.168.1.50 | 48213 bytes | snapshot.jpg
```

Jika foto tersebut tetap ingin disimpan, centang *Simpan foto yang formatnya tidak sesuai*
(foto masuk ke `_tidak_sesuai`). Tombol **Buka log txt** membuka folder `_log`.

### Log txt per hari

Semua data ditulis ke folder `_log` di dalam folder tujuan. Setiap hari otomatis dibuat file
baru (berganti tepat jam 00:00, walau aplikasi tetap berjalan):

| File | Isi |
|---|---|
| `diterima_YYYY-MM-DD.txt` | semua file yang diterima: waktu, pengirim, status, nama asli, nama baru, code, ukuran, keterangan |
| `log_YYYY-MM-DD.txt` | semua baris log (koneksi, login, disimpan, duplikat, error) |
| `tidak_sesuai_YYYY-MM-DD.txt` | hanya file yang formatnya tidak sesuai |

Contoh `diterima_2026-10-14.txt`:

```
# waktu | dari | status | nama asli | nama baru | code | bytes | keterangan
2026-10-14 12:17:41 | 192.168.1.50 | Disimpan | https&&&aslibos.com&scan&BXXAXESPP2026_10_14_12_16_53.jpg | 00001_20261014_121653_BXXAXESPP.jpg | BXXAXESPP | 48213 |
2026-10-14 12:17:41 | 192.168.1.50 | Duplikat | https&&&aslibos.com&scan&BXXAXESPP2026_10_14_12_16_53.jpg | 00001_20261014_121653_BXXAXESPP.jpg | BXXAXESPP | 48213 | Code sudah pernah disimpan
```

File txt bisa dibuka dengan Notepad saat aplikasi sedang berjalan.

Folder khusus di dalam folder tujuan:

| Folder | Isi |
|---|---|
| `_log` | log txt harian (lihat di atas) |
| `_tidak_sesuai` | foto yang formatnya tidak sesuai, hanya jika opsinya dicentang |
| `_duplikat` | duplikat, hanya jika opsinya dicentang |
| `.incoming` | file yang sedang diterima (sementara) |

## Kolektor (TCP/IP client, CSV per batch)

Menu **Kolektor** punya **koneksi sendiri lewat IP** (bukan FTP). Aplikasi ini adalah **client**:
ia menyambung ke **IP + Port server** (alat/scanner/PLC/PC yang mengirim data) dan menerima data darinya.
Rename foto tetap berjalan lewat FTP di Dashboard, keduanya tidak saling tercampur.

1. Isi **Nama file**: `Alb-` + angka (diisi manual, mis. `000123` → `Alb-000123`).
2. Isi **IP Server** dan **Port** yang mengirim data (mis. `192.168.1.50` port `9004`).
3. Pilih **Folder CSV** (default `folder tujuan\collect`).
4. Klik **Start** → CSV dibuka/dikunci (`Alb-000123.csv`), nama batch + IP/Port terkunci,
   aplikasi menyambung ke server. Status koneksi tampil di kanan atas (hijau = terhubung).
5. Setiap link yang diterima dicatat satu baris. **Duplikat diabaikan** (link yang sama persis).
   Link juga bisa ditempel di kotak *Tambah manual* (ikut aturan yang sama).
6. Klik **Done** bila selesai (koneksi ditutup, nama batch terbuka lagi, nomor otomatis naik).
7. **Export CSV** membuat salinan CSV ke lokasi lain kapan saja.

Isi CSV hanya **2 kolom**:

```
Data;Timestamp
https://aslibos.com/scan/BXXAXESPP;2026-10-16 08:00:01
https://aslibos.com/scan/BXXAXES8P;2026-10-16 08:00:03
https://aslibos.com/scan/VZJZ35QD7;2026-10-16 08:00:03
```

Aturan tanda `;` dalam satu kiriman:

| Data yang diterima | Hasil di CSV |
|---|---|
| `https://aslibos.com/scan/BXXAXESPP` | 1 baris |
| `https://aslibos.com/scan/BXXAXESPP;https://aslibos.com/scan/BXXAXESPP` | 1 baris (sama, yang setelah `;` dibuang) |
| `https://aslibos.com/scan/BXXAXES8P;https://aslibos.com/scan/VZJZ35QD7` | 2 baris: `BXXAXES8P`, lalu `VZJZ35QD7` di baris bawahnya |
| link yang sudah pernah masuk di batch ini | diabaikan (dihitung di "Duplikat diabaikan") |

Link dari satu kiriman mendapat timestamp yang sama. Tabel di layar urutannya sama dengan CSV
(data terbaru di bawah).

- **Timestamp** = waktu data diterima aplikasi (`YYYY-MM-DD HH:MM:SS`).
- Satu data = satu pesan dari server, diakhiri `CR`, `LF`, `CRLF`, `ETX` atau `NUL`
  (bingkai `STX ... ETX` juga dikenali). Kalau server mengirim tanpa akhiran, data dianggap
  selesai setelah jeda singkat (0,3 detik).
- Kalau server belum aktif atau koneksi putus, aplikasi **menyambung ulang otomatis** tiap 3 detik
  selama sesi masih Start. Kejadian sambung/putus dicatat di **Log Aktivitas**.
- Baris ditulis ke CSV secara langsung (aman walau aplikasi ditutup); memulai batch yang sama lagi
  akan melanjutkan tanpa menggandakan data lama. File lama dengan kolom lain tidak akan ditimpa
  (aplikasi meminta nomor batch lain).
- CSV memakai pemisah `;` dan UTF-8 BOM, jadi langsung rapi dibuka di Excel (Indonesia).
- Coba tanpa alat: jalankan `python tools/test_tcp_server.py --port 9004`, lalu di Kolektor isi
  IP `127.0.0.1` port `9004` dan klik Start.

## Aktivasi (model patch, HWID + registry + OTP)

Aplikasi ini dikunci per komputer. Perlindungan ini untuk aplikasi Anda sendiri — bukan alat untuk
membuka software orang lain.

Cara kerja:

- Saat dibuka, kalau belum aktif, muncul jendela **Aktivasi**. Di situ ada **ID Komputer (HWID)**,
  dihitung dari identitas mesin (di Windows: *MachineGuid* registry + *volume serial* C: + MAC), lalu di-hash.
- Pelanggan mengirim HWID itu ke nomor vendor (default **085772869284**, WhatsApp/SMS) dan menerima
  **Kode Aktivasi** + **OTP**.
- Kode = tanda tangan **Ed25519** atas `HWID | nama | masa berlaku | OTP`. Aplikasi memverifikasi
  dengan **kunci publik** vendor yang tertanam. Karena yang tertanam hanya kunci publik, kode **tidak
  bisa dipalsukan** tanpa kunci privat vendor, dan hanya berlaku di komputer ber-HWID itu.
- Setelah berhasil, aktivasi disimpan di **registry** (HKCU) **dan** file cadangan, dan diverifikasi
  ulang terhadap HWID setiap kali dibuka (menyalin registry/file ke PC lain tidak berguna).
- Bisa juga memuat file **`.lic`** (tombol *Muat file .lic*) atau mengarahkan env `FRTCAM_LICENSE_FILE`
  ke file lisensi (untuk lisensi massal).

### Membuat kode aktivasi (khusus vendor)

Ada **2 cara**. Pakai salah satu.

**Cara 1 - aplikasi (GUI), paling mudah.** Build sekali dengan `build_activation.bat`:

```
dist\FRTCam-Aktivasi.exe
```

Buka aplikasinya, tempel HWID dari pelanggan, pilih masa berlaku, klik **Buat Kode** →
muncul **Kode Aktivasi** + **OTP** yang tinggal disalin/dikirim, atau **Simpan file .lic**.
Tombol **Buat kunci vendor sendiri** membuat kunci Anda (sekali). Simpan `.exe` ini untuk Anda
sendiri — **jangan** dibagikan ke pelanggan.

**Cara 2 - command line.** `tools/license_tool.py` (butuh Python):

```
python tools\license_tool.py keygen --write     # buat kunci vendor Anda sendiri (SEKALI), tulis kunci publik ke app, lalu build ulang
python tools\license_tool.py issue --hwid <HWID dari pelanggan> --name "PT Contoh" --days 0 --out kode.lic
```

- `--days 0` = selamanya; `--days 365` = sewa 1 tahun. OTP dibuat acak (atau `--otp 123456`).
- Kirim **KODE AKTIVASI** + **OTP** ke pelanggan (mis. via WhatsApp dari nomor vendor), atau kirim file `kode.lic`.
- **Penting:** sebelum program dibagikan, jalankan `keygen` untuk memakai kunci Anda sendiri. Sebelum itu,
  dipakai **kunci DEMO** bawaan yang kuncinya diketahui umum (siapa pun bisa membuat kode) — hanya untuk uji coba.
- Nomor vendor bisa diganti di `gui/activation.py` (`VENDOR_PHONE`). Aplikasi tidak mengirim SMS sendiri
  (menghindari penyalahgunaan); pengiriman OTP dilakukan manual lewat nomor vendor, atau integrasikan
  gateway SMS Anda sendiri bila perlu.

Mengirim OTP SMS otomatis **sengaja tidak dibuat** di dalam aplikasi, supaya file `.exe` yang tersebar
tidak bisa dipakai membanjiri satu nomor dengan SMS.

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
2. Pilih **Mode koneksi**:
   - **Server**: isi IP lokal, Port (default 21), Username, Password. Di setting FTP kamera,
     isi IP komputer ini, port, username dan password yang sama.
   - **Client**: isi IP server FTP, Port, Username, Password, Folder remote, interval cek,
     jumlah download paralel, dan centang *Hapus file di server* jika perlu.
3. Isi **LINE-ID** (mis. `00001`) dan pilih **Folder tujuan** dengan tombol *Browse...*.
4. Klik **Mulai Server** / **Mulai Client**. Saat pertama kali jalan, izinkan akses di jendela
   *Windows Firewall*.

### Uji tanpa kamera

```
.venv\Scripts\python tools\test_upload.py --host 127.0.0.1 --port 21 --user admin --password admin
```

Script ini mengirim 5 file (format lama dan format `https&&&...`): 2 tersimpan, 2 duplikat,
1 format tidak sesuai (hanya dicatat di log).

## Struktur proyek

```
backend/        backend C# (FtpBackend.exe)
  Program.cs          argumen, mode server/client, perintah dari GUI (stdin)
  FtpServer.cs        mode server: listener + sesi paralel
  FtpSession.cs       mode server: protokol FTP per koneksi
  FtpClient.cs        mode client: protokol FTP client (PASV/EPSV, MLSD/LIST, RETR, DELE)
  FtpPuller.cs        mode client: scan berkala + download paralel
  PhotoProcessor.cs   rename + anti duplikat
  AsyncUtil.cs        helper timeout
  EventSink.cs        event JSON ke GUI (stdout) + log txt harian
  DailyTextLog.cs     file txt yang berganti setiap hari
gui/            GUI PySide6
  main.py             entry point
  main_window.py      jendela utama (menu samping, dashboard, halaman lain)
  theme.py            warna + style sheet tema gelap
  icons.py            ikon garis (SVG) untuk semua tombol
  widgets.py          kartu, kartu statistik, grafik aktivitas, transfer, toggle, penampil foto
  photo_panel.py      panel foto terakhir disimpan (zoom, layar penuh, thumbnail)
  received_table.py   tabel File Diterima (filter, auto-refresh, tombol lihat)
  stats.py            hitungan sejak dibuka, hari ini, aktivitas per detik/menit
  backend_client.py   menjalankan backend (QProcess)
  naming.py           preview aturan rename
  app_config.py       simpan/muat config.json
  collector.py        kolektor: sesi batch + tulis CSV (Data, Timestamp) + anti duplikat
  collector_page.py   halaman Kolektor (IP + Port, Start/Done)
  tcp_receiver.py     client TCP/IP kolektor (sambung ulang otomatis)
  activation.py       aktivasi: HWID + kode Ed25519 + OTP (verifikasi)
  activation_dialog.py jendela aktivasi (aplikasi utama)
  vendor_app.py       aplikasi PEMBUAT LISENSI (khusus vendor)
  ed25519.py          tanda tangan Ed25519 (pure Python)
  hwid.py             hitung HWID komputer
  license_store.py    simpan aktivasi di registry + file
tools/test_upload.py  kirim foto uji
tools/test_tcp_server.py server TCP uji untuk Kolektor
tools/license_tool.py pembuat kode aktivasi (command line, khusus vendor)
assets/app.ico        ikon aplikasi (.exe)
build.bat             build aplikasi utama -> dist\FtpPhotoRenamer.exe
build_activation.bat  build pembuat lisensi -> dist\FRTCam-Aktivasi.exe
```

GUI menjalankan `FtpBackend.exe` sebagai proses terpisah. Backend mengirim event JSON per baris
(stdout), dan GUI mengirim perintah `STOP` / `SET LINEID <id>` lewat stdin. Backend juga bisa
dijalankan sendiri dari command prompt (`FtpBackend.exe --help`).
