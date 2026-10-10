pm3tool — GUI Referensi, Revisi 3

JALANKAN
1. Ekstrak seluruh ZIP ke folder baru.
2. Windows: jalankan run.bat atau run_pm3.bat, dengan Python 3.10+.
   Launcher asli akan memasang PySide6 jika belum tersedia.
   Linux: ./run.sh. Alternatif: python -m pm3tool gui
3. Pilih client PM3 dan gunakan Auto Detect seperti sebelumnya.

TAMPILAN
Ketujuh halaman mengikuti posisi dan ukuran referensi pada 1536 x 1024:
Reader, Dump Viewer, Clone, Write Data / Recycle, Firmware,
Recovery Keys, dan Write Chip Ink Baru.

Logo, ikon navigasi, ikon aksi, ikon perangkat, kalender, dan bingkai
panel/tombol/input/tab diambil dari tujuh gambar yang Anda lampirkan.
Daftar sumber dan koordinat crop tersedia di ui_assets/reference_assets.json.
Font disertakan agar ukuran dan proporsi teks konsisten di Windows/Linux.

Input, dropdown, checkbox, tombol, navigasi, tabel dan konsol tetap widget
Qt nyata. Bingkai gambar hanya menjadi skin elemen; teks, data, interaksi,
status dan hasil operasi ditampilkan langsung oleh aplikasi.
Tabel Reader dan Recovery terhubung ke model hasil recovery asli.
Dump Viewer menampilkan file yang sebenarnya, termasuk filter sektor dan
format Hex/ASCII. Tampilan teks asli tersedia melalui tombol Teks / Tabel.
Ringkasan preview recycle, form lanjutan recovery dan validasi ink tetap ada.

Drag area header untuk memindahkan jendela. Tombol kanan atas berfungsi
untuk minimize, maximize dan close. Ukuran jendela mengikuti layar;
koordinat, teks dan ikon menyesuaikan ketika jendela diperkecil.

FUNGSI ASLI
Modul backend, algoritma, validasi, konfirmasi operasi, launcher dan
file acuan ink identik dengan ZIP asal. Di gui_qt.py hanya __init__ yang
memasang lapisan presentasi baru. Tidak ada handler operasi yang diganti.
GUI Tk asli juga tetap tersedia seperti sebelumnya.

PREVIEW
previews/0.png — Reader
previews/1.png — Dump Viewer
previews/2.png — Clone
previews/3.png — Write Data / Recycle
previews/4.png — Firmware
previews/5.png — Recovery Keys
previews/6.png — Write Chip Ink Baru
previews/compact.png — jendela 1100 x 800
Screenshot berasal dari aplikasi Qt yang berjalan. Dump Viewer menggunakan
file acuan ink asli yang dibundel. Koneksi, log dan hasil contoh pada gambar
referensi tidak dimasukkan sebagai hasil perangkat yang belum dijalankan.

VALIDASI
181 pengujian lulus, termasuk alur preview/write dengan simulator, validasi,
callback asli, Copy/Clear, filter dump, akses form lanjutan, resize dan
pembaruan model tabel recovery. Backend dibandingkan dengan ZIP asal.
Pengujian dilakukan dengan Qt offscreen di Linux; operasi pada perangkat
Proxmark3 fisik di Windows belum dijalankan di lingkungan ini.

KODE PRESENTASI
pm3tool/reference_ui.py — widget, tata letak, skin dan binding tampilan
pm3tool/neon_ui.py — entry point pemasangan tampilan
pm3tool/ui_assets/ — aset potongan referensi, font dan lisensinya
Tools ekstraksi/font/capture tersedia di tools/ untuk pengembangan saja;
menjalankan software tidak memerlukan Pillow, NumPy atau fontTools.
