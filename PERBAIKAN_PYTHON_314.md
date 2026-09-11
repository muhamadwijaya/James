# Perbaikan instalasi Python 3.14

Paket sebelumnya mengunci PySide6 6.8.3, yang memerlukan Python di bawah 3.14.
Log pip yang menolak versi itu dan menawarkan PySide6 6.10.1 atau lebih baru
konsisten dengan Python 3.14. Launcher lama juga memeriksa versi 6.8.3 secara
langsung, sehingga mengubah requirements saja belum memperbaiki seluruh alur.

## Jalankan paket pembaruan

1. Tutup launcher yang menampilkan error.
2. Ekstrak ZIP pembaruan. Boleh mengganti file source pada folder AGREGASI_UI
   sebelumnya, atau gunakan folder baru.
3. Klik dua kali **JALANKAN_AGREGASI.bat** dari folder pembaruan itu.
4. Launcher menampilkan versi Python, lalu memasang PySide6 yang sesuai:
   - Python 3.10–3.13: PySide6 6.8.3.
   - Python 3.14: PySide6 6.10.3.
5. Tunggu instalasi selesai. Dashboard kemudian dibuka otomatis.

Tidak perlu menghapus `.venv` jika interpreter lamanya masih bekerja. Launcher
memeriksa seluruh komponen PySide6 dan memperbaruinya bila diperlukan. Data
aplikasi yang tersimpan di lokasi aplikasi Windows tetap digunakan.

## Cara manual melalui CMD

Buka CMD di folder **paket pembaruan**. Jika `.venv` sudah dibuat:

```bat
.venv\Scripts\python.exe runtime_check.py
.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
.venv\Scripts\python.exe runtime_check.py --dependencies
.venv\Scripts\python.exe main.py
```

Jika `.venv` belum ada, jalankan `py -3 -m venv .venv` terlebih dahulu.

Paket memerlukan Python standar 64-bit (CPython), bukan build free-threaded.
Pemeriksaan awal memberi pesan spesifik untuk interpreter di luar rentang yang
didukung. Instalasi pertama membutuhkan internet; setelah terpasang, operasi
lokal tetap dapat berjalan offline.

Metadata resmi PySide6 6.10.3 mencantumkan Python >=3.9,<3.15 dan menyediakan
wheel Windows x86-64: https://pypi.org/project/PySide6/6.10.3/
