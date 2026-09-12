# Agregasi tahap 1, template print terkunci, dan printer TIJ — v3.12.0

**Halaman Tahap 1 / BOX kini terbagi dua.** Separuh kiri tetap grid unit dengan
**ukuran sel yang sama seperti sebelumnya**; lima sel per baris dan lima baris
terlihat sekaligus. Jumlah sel mengikuti **target maksimum agregasi** pada
template yang dipilih, dan sisanya dicapai dengan **scroll ke bawah** (roda mouse
di atas grid atau bilah gulir di sisi kanan panel). Baris yang sedang dipindai
selalu ikut terlihat. Separuh kanan menampilkan **template print yang dikunci** —
label persis seperti yang akan dicetak, lengkap dengan kode box, ukuran canvas,
DPI, jenis printer, dan penanda cetak otomatis saat maksimum.

**Di bawah template print** tampil **data master box yang menunggu verifikasi**
(kode box, produk, batch/MFD, isi box, status cetak dan verifikasi) selama
scanner gun dipakai. Bila scanner tahap 1 memakai kamera, area yang sama berubah
menjadi **tampilan kamera** beserta status koneksinya.

**Pilihan scanner ada langsung di halaman Box.** Panel kanan bawah memuat
**MODE SCAN** (`SCANNER GUN` / `KAMERA IP`); saat mode kamera dipilih, kolom
**IP** dan **PORT** beserta tombol **SAMBUNG** muncul di panel yang sama. Pilihan
ini disimpan ke profil scanner tahap 1, jadi halaman Pengaturan langsung ikut
berubah, dan sebaliknya.

**Pengaturan → Scanner** memiliki **MODE SCAN** untuk setiap scanner tahap:
`SCANNER GUN` (port COM atau keyboard seperti sebelumnya) atau `KAMERA IP`
dengan **IP KAMERA** dan **PORT KAMERA** yang dapat diisi. Mode kamera mengambil
snapshot HTTP berkala, menampilkannya pada halaman Box, lalu mengirim barcode
yang terbaca ke kolom scan. Frame kosong atau gambar yang gagal dibaca tidak
pernah dilaporkan sebagai hasil scan; statusnya ditulis apa adanya.

**Urutan pemilihan data dibalik.** Template dipilih paling awal dan daftarnya
hanya berisi master template yang **tersimpan dan aktif**. Produk tidak dipilih
manual lagi: nilainya mengikuti relasi child pada template dan hanya ditampilkan.
Setelah batch dan list data ditentukan, tombol **KUNCI DATA / BUKA KUNCI DATA**
mengunci pilihan tersebut dan menyiapkan sesi agregasi. Scanner kemudian
memverifikasi otomatis setiap unit yang sesuai template dan list data terkunci;
data hanya dapat dibuka kembali selama box belum berisi unit.

**Tombol START CONVEYOR dihapus** dari Tahap 1, 2, dan 3. Pada halaman Box
tempatnya diisi **KUNCI BOX** untuk mengunci box sebelum target maksimum.

**Progres agregasi menampilkan target maksimum template yang dikunci**
(`MAX TEMPLATE n`). Saat jumlah maksimum tercapai, label agregasi **dicetak
otomatis**, termasuk untuk template bermode Manual print. Pilihan Auto/Manual
pada template sekarang mengatur pencetakan ketika box dikunci sebelum maksimum.

**Master Template**: ukuran canvas (**Lebar** dan **Tinggi**) serta **DPI CETAK**
diatur langsung pada form template BOX, CARTON, dan PALLET. Khusus template BOX
(agregasi tahap 1) tersedia **JENIS PRINTER**: `Printer label` atau
`TIJ / thermal`. Bila TIJ dipilih, **KONEKSI TIJ** meminta IP dan port print head
thermal, dan label agregasi dikirim langsung ke alamat tersebut. Dokumen template
menyimpan jenis printer beserta alamatnya, sehingga pilihan ini ikut berpindah
saat template diekspor atau diimpor.

---

# Tata letak seragam v3.11.2

Ukuran dan posisi tulisan **AGREGASI**, subjudul, serta informasi Line / Shift /
User sekarang menggunakan satu header bersama. Berpindah halaman hanya mengganti
isi subjudul, tanpa mengganti ukuran hurufnya.

Batas kiri, atas, kanan, dan bawah area konten disamakan untuk Dashboard, Box,
Carton, Pallet, Revision, Kirim Data, Pengaturan, dan Master Template. Panel,
formulir, tabel, serta area klik mengikuti batas yang sama ketika layar berubah.
Delapan tombol navigasi bawah memiliki lebar, tinggi, jarak, dan perataan sama.
Tombol Master Template tidak lagi lebih lebar. Dua tab Pengaturan juga disamakan.

**Jalankan:** ekstrak ZIP ke folder baru, lalu buka **JALANKAN_AGREGASI.bat**.
Pengaturan font, ikon, resolusi, dan mode layar yang tersedia tetap dapat digunakan.

Pratinjau: `docs/layout_seragam_v3_11_2/`.
Hasil pemeriksaan: `docs/VALIDASI_LAYOUT_v3_11_2.txt`.

---

# Perbaikan lebar penuh v3.11.1

**Mode Pas layar kini mengisi seluruh lebar dan tinggi jendela**, termasuk pada
layar 1920 × 1280 dan 1920 × 1080. Ruang kosong besar di kiri dan kanan dihapus.
Panel dan area kerja melebar mengikuti rasio jendela. Teks, ikon SVG dan
indikator lingkaran tetap proporsional. Area klik ikut menyesuaikan posisi.

Ekstrak paket ke folder baru, lalu jalankan **JALANKAN_AGREGASI.bat**.
Pengaturan Pas layar yang sudah tersimpan langsung memakai perilaku baru.
Di **Pengaturan → Tampilan**, pilih **MAKSIMAL** untuk memenuhi area kerja
layar atau **LAYAR PENUH** untuk menyembunyikan bilah judul. Mode Jendela juga
mengisi seluruh area konten jendelanya.

Pratinjau dan hasil pemeriksaan: `docs/lebar_penuh_v3_11_1/`.

---

# Pembaruan tampilan aplikasi v3.11.0

Buka **Pengaturan → Tampilan** untuk mengatur resolusi, mode jendela, font,
ikon, kepadatan tabel, sudut elemen, dan sorotan hover. Tekan **Terapkan dan
Simpan** untuk menerapkan ke seluruh halaman. Pengaturan tersimpan di database
lokal dan digunakan kembali saat aplikasi dibuka.

Panel kanan menggunakan satu susunan bersama sesuai contoh Box. Posisi kartu,
aktivitas, informasi sistem, akun dan shortcut sama di semua halaman. Nilai,
judul ringkasan dan data aktif mengikuti halaman. Ikon Pengaturan sekarang
berupa roda gigi kecil, simetris, dengan garis halus.

**Jalankan:** ekstrak seluruh ZIP, lalu buka `JALANKAN_AGREGASI.bat`.
Gunakan folder hasil ekstrak yang baru agar berkas aplikasi lama tidak tertinggal.
Database pada direktori data aplikasi tetap digunakan. Paket mendukung Python
3.10–3.14 64-bit melalui launcher yang sudah disertakan.

- Mode **Maksimal** atau **Layar penuh** mengikuti layar aktif.
- Mode **Jendela** memakai preset dari 800 × 600 sampai 1920 × 1280.
- **Pas layar** mempertahankan proporsi dan menampilkan seluruh kanvas.
- **Ukuran asli (scroll)** mempertahankan ukuran dasar untuk layar kecil.
- Font 90–115%, ikon 80–120%, kepadatan tabel Rapat/Normal/Lega.

Panduan lengkap: [Pengaturan tampilan](docs/PANDUAN_TAMPILAN.md).
Pratinjau terbaru: `docs/tampilan_v3_11/`.
Validasi versi ini: `docs/VALIDASI_TAMPILAN_v3_11.txt`.

Riwayat pembaruan di bawah menjelaskan fitur dan pengujian versi sebelumnya.

---

# Pembaruan Agregasi Pallet lengkap — v3.10.0

Halaman PALLET mengikuti acuan: empat menu proses, grid 6 × 4 dengan animasi scan,
produk/batch/list/template, MFD, lima scan dan lima hasil terakhir, kontrol line,
printer, verifikasi, serta upload. Semua terhubung ke sesi dan relasi database.

Target list dapat dipilih atau diimpor dari CSV. Validasi mencegah carton salah
produk/batch/template, duplikat, belum tercetak, atau sudah dimiliki pallet lain.
Kamera USB/IP membaca barcode nyata; revisi isi membatalkan verifikasi dan meminta
cetak ulang label terkait. Sesi tersimpan dapat dilanjutkan setelah aplikasi dibuka.

Mulai dari [Panduan Pallet](docs/PANDUAN_PALLET.md).
Pratinjau: `docs/pallet_lengkap/pallet-lengkap.png` dan
`docs/pallet_lengkap/Pallet_Lengkap_4K_v3_10.png`.
**156 kasus pengujian unik lulus** (dijalankan dalam kelompok).
Hasil lengkap: `docs/VALIDASI_PALLET.txt`.
Paket ini melanjutkan v3.9 dan mempertahankan Pengaturan, Box, Carton, Revisi,
Upload serta Master Template sebelumnya. Perangkat produksi belum diuji langsung.

---

# Pembaruan Agregasi Carton lengkap — v3.9.0

Halaman CARTON mengikuti acuan dengan grid 4 × 3, daftar target box,
produk/batch/list/template, MFD, riwayat scan, hasil carton, kontrol line,
printer, verifikasi operator, dan upload. Sidebar tetap memakai ukuran bersama.

Mulai dari [Panduan Carton](docs/PANDUAN_CARTON.md).
Pratinjau ada di `docs/carton_lengkap/carton-lengkap.png` dan
`docs/carton_lengkap/Carton_Lengkap_4K_v3_9.png`.
Paket ini juga memuat pembaruan Box, Revisi, Upload, dan Pengaturan sebelumnya.

---

# Pembaruan Agregasi Box lengkap — v3.8.0

Halaman BOX mengikuti acuan dengan grid 50 unit, pilihan produk/batch/list/template,
riwayat scan, hasil box, kontrol line, MFD, dan ringkasan dari data sesi tersimpan.
Bingkai sidebar tetap sama di seluruh halaman. Ikon menggunakan SVG vektor.

Mulai dari [Panduan Box](docs/PANDUAN_BOX.md). Pratinjau tersedia di
`docs/box_lengkap/box-lengkap.png` dan versi 4K `Box_Lengkap_4K_v3_8.png`.

---

# Pembaruan Revisi lengkap — v3.7.0

Pencarian per level, rentang tanggal, filter, pengurutan/paginasi, detail relasi,
traceability, enam aksi revisi dan log sebelum–sesudah sudah terhubung ke database.
Pemindahan parent memeriksa batch/kapasitas dan memperbarui quantity sesi terkait.
Cetak ulang tersedia melalui pratinjau, PDF, serta printer yang dikonfigurasi.

Mulai dari [Panduan Revisi](docs/PANDUAN_REVISI.md).
Pratinjau terbaru: `docs/revisi_lengkap/revisi-lengkap.png`.
Pengaturan lengkap dan Upload lengkap tetap termasuk dalam paket ini.
Hasil pengujian: `docs/VALIDASI_REVISI.txt`.

---

# Pembaruan Upload / Kirim Data lengkap — v3.6.0

Halaman Upload mengikuti acuan dan terhubung ke antrean SQLite serta API nyata.
Filter level/batch/tanggal/status, pilihan lintas halaman, validasi, backup,
CSV/XLSX/PDF, impor deduplikat, riwayat percobaan, retry, auto sync, dan pause
sudah berfungsi. Pengaturan lengkap dan halaman sebelumnya tetap tersedia.

Mulai dari [Panduan Upload](docs/PANDUAN_UPLOAD.md) untuk penggunaan dan kontrak
server. Ganti Project URL contoh dan token di Pengaturan untuk menghubungkan
server produksi. Status sukses memerlukan pengakuan server.

Pratinjau: `docs/upload_previews/upload-lengkap.png`.
Hasil pengujian: `docs/VALIDASI_UPLOAD.txt`.

---

# Pembaruan Pengaturan lengkap — v3.5.0

Halaman Pengaturan kini mengikuti acuan dengan 53 kontrol dan 17 tombol aksi.
Simpan/muat ulang, validasi, profil pengguna, backup/restore, ekspor log,
kalibrasi serial/USB, cetak driver/ZPL, pemeriksaan koneksi dan antrean HTTP
sudah dihubungkan ke fungsi aplikasi.

**Mulai dari [Panduan Pengaturan](docs/PANDUAN_PENGATURAN.md)** untuk rincian
setiap kontrol, koneksi perangkat dan kontrak API server.
Tampilan terbaru: `docs/settings_previews/pengaturan-lengkap.png`.
Hasil pengujian: `docs/VALIDASI_PENGATURAN.txt`.

Kontrol optik scanner industri/kamera IP masih membutuhkan SDK vendor.
Profil user lokal belum merupakan autentikasi dan otorisasi server produksi.
Gunakan driver, IP perangkat dan Project URL yang benar sebelum tes perangkat.

---

# AGREGASI — Dashboard desktop PySide6

Dashboard software agregasi yang dibangun ulang dari referensi `dashboard1.png`.
Semua panel, teks, grafik, progress, dan indikator digambar menggunakan Qt/QPainter;
18 ikon berasal dari SVG vektor. Aplikasi tidak menggunakan screenshot sebagai
background. Desain dasar 1448 × 1086 mengikuti proporsi referensi dan diskalakan
secara proporsional mengikuti monitor tanpa scrollbar. Pada layar dengan rasio
berbeda, ruang tepi menjaga bentuk huruf dan ikon tetap alami. Semua menu utama dibuka
sebagai halaman internal di dalam satu jendela (bukan popup).

## Live preview lima template tersimpan

Indikator SERIAL/UNIX, sumber child, dan Auto/Manual print diperkecil menjadi
bulatan hijau solid. Live preview menampilkan **maksimal 5 template tersimpan**
sesuai halaman BOX, CARTON, atau PALLET. Tombol **Sebelumnya / Berikutnya** dan
nomor halaman muncul di bawah kartu jika jumlah template lebih dari lima.

Klik kartu untuk memuat template di editor. Draft tetap terlindungi oleh dialog
perubahan belum disimpan. Galeri diperbarui setelah Simpan; setiap level mengingat
halaman galerinya sendiri. Nama lengkap tersedia pada tooltip kartu.

Tampilan: [docs/saved_gallery_previews/carton_page_1.png](docs/saved_gallery_previews/carton_page_1.png).
Screenshot menggunakan katalog contoh sementara berisi 12 template per level;
data contoh tambahan tidak dimasukkan ke database aplikasi pengguna.

## Produk child, bypass BOX, target, dan mode cetak

BOX kini memilih produk child dari combobox database. CARTON mempunyai pilihan
saling eksklusif **Lewat BOX** atau **Produk child** langsung. PALLET tetap
memilih CARTON. Setiap template menyediakan **TARGET QTY Min/Max** dan
**Auto print / Manual print** di bawah Link Child.

Saat Simpan, ID child, jalur agregasi, target, mode cetak, dan dokumen lengkap
tersimpan ke tabel **template_agregasi** dalam SQLite aplikasi. Gunakan tombol
**…** pada pilihan produk untuk menentukan database/tabel/kolom ID dan nama.

Halaman tahap menyediakan pilihan template tersimpan dan sesi agregasi lokal.
Quantity, pencegahan duplikat, relasi antarhasil BOX/CARTON/PALLET, batas Min/Max,
serta pemicu cetak mengikuti snapshot template. Auto print menggunakan printer
default saat Max tercapai; Manual print menunggu tombol Print Label. Sumber
produk eksternal dibaca tanpa dimodifikasi.

Panduan: [docs/PANDUAN_AGREGASI_CHILD.md](docs/PANDUAN_AGREGASI_CHILD.md).
Tampilan terbaru: [docs/child_target_previews/carton_direct_child.png](docs/child_target_previews/carton_direct_child.png).
**65 tes lulus** pada Qt/Linux. Printer fisik dan desktop Windows belum diuji
langsung. Input UNIT lokal diikat ke produk pilihan; verifikasi serial terhadap
server dan integrasi scanner/kamera fisik belum termasuk adapter ini.

## Revisi 11 poin: preview, dialog, field database, dan NIE

- Live preview hanya menampilkan template pada level aktif.
- Preview Print menyesuaikan gambar dengan ukuran pop-up tanpa memotong label.
- Dialog hapus, notifikasi, ukuran kertas, dan riwayat terpisah dari canvas yang
  diskalakan; tombol konfirmasi memakai tema navy yang sama.
- Ikon baris sidebar diperkecil menjadi 14 × 14 px dengan bingkai lingkaran
  proporsional. Shortcut bawah memiliki jarak dari border.
- Dropdown, scrollbar, dan kontrol angka memakai warna tema yang menyatu.
- Pilihan Template Print dihapus. Form, data, dan desain disimpan bersama
  dalam satu master; preview dan cetak membaca dokumen yang sama.
- Nama Produk ditambahkan pada form; Link Child UNIT kini dipilih dari combobox produk database.
- NIE tersedia pada form dan dapat dicetak melalui `{{nie}}`.
- **Data → Database** memilih file SQLite dan tabel/view sumber. Field diurutkan
  sesuai kolom asli; nama yang tidak ditemukan ditandai merah. Sumber eksternal
  hanya dibaca dan tidak dimodifikasi.

**65 tes lulus** pada Linux/PySide6, termasuk preview pada beberapa ukuran,
konfirmasi hapus/batal/simpan, persistensi NIE, schema database terpisah,
barcode/QR/DataMatrix, dan navigasi. Dialog desktop Windows dan printer fisik
masih memerlukan uji pada perangkat pengguna. Adapter sumber field yang
tersedia pada revisi ini adalah SQLite.

Screenshot terbaru: `docs/revision_previews/`; panduan alur database dan
penggunaan editor: `docs/PANDUAN_TEMPLATE_EDITOR.md`.

## Tampilan mengikuti referensi terbaru

Panel kiri diperlebar untuk form dan daftar enam kolom; canvas, live preview,
ringkasan, penggunaan, printer, histori, informasi sistem, akun, dan shortcut
mengikuti susunan gambar terbaru. Selector atas memilih BOX/CARTON/PALLET; menu kecil pada form kembali
ke **Template, Objek, Data** seperti versi sebelumnya. Ikon box, carton, dan pallet disesuaikan dengan referensi.

Tombol memiliki gradasi, sorotan hover dengan transisi singkat, status tekan,
dan fokus keyboard. Ring aktif beranimasi ketika nilainya berubah. Jumlah,
status, penggunaan hari ini, dan aktivitas berasal dari database; pembaruan
berjalan setiap tiga detik. Angka contoh pada referensi tidak dijadikan statistik
produksi. Ukuran dan bentuk label pada layar tetap mengikuti ukuran fisik cetak.

Form menyediakan Nama Produk, GTIN, NIE, SERIAL/UNIX, link child,
informasi terpilih, dan status aktif. Daftar memuat empat
baris per halaman dengan tombol sebelumnya/berikutnya. **Lihat semua** membuka
riwayat lengkap dengan pencarian. Ikon kertas pada toolbar membuka ukuran/DPI;
ikon form, roda gigi, dan `{}` membuka form template, properti objek, dan data.

**65 tes lulus**, termasuk kontrol baru, pagination, status, dokumen desain,
riwayat, dan penghentian timer saat aplikasi ditutup. Pemeriksaan berlangsung
di Linux/PySide6; perangkat fisik dan Supabase belum terhubung di lingkungan ini.

## Editor template BOX, CARTON, PALLET

Tiga selector membuka **tiga workspace independen**, masing-masing memiliki
form, daftar template, canvas, data, dan riwayat undo sendiri. Ikon selector,
toolbar, toolbox, penggaris, grid, label cetak, dan live preview mengikuti
susunan referensi editor. Warna navy dan biru aktif tetap konsisten antarmenu.

Canvas mendukung drag, resize, pilihan beberapa objek, undo/redo, clipboard,
perataan, jarak, lapisan, zoom, teks, gambar/logo, simbol, field dinamis, serta
**Code128, QR, dan DataMatrix yang benar-benar dienkode**. Simpan, duplikasi,
hapus, default, impor/ekspor JSON, PNG/PDF, preview, dan publikasi lokal memakai
data nyata di SQLite. Test Print membuka printer sistem; bila tidak ada printer,
aplikasi menawarkan PDF. Publikasi menyimpan snapshot versi di database lokal.

Panduan lengkap: [docs/PANDUAN_TEMPLATE_EDITOR.md](docs/PANDUAN_TEMPLATE_EDITOR.md).
Tampilan terbaru: [docs/template_previews/pallet.png](docs/template_previews/pallet.png),
[BOX](docs/template_previews/box.png), dan [CARTON](docs/template_previews/carton.png).
Hasil pengujian terbaru ada di [docs/VALIDASI_TEMPLATE.md](docs/VALIDASI_TEMPLATE.md).

## Revisi navigasi mengikuti referensi kedua

Navigasi bawah kini memakai komponen bersama `agregasi/navigation.py` untuk
seluruh delapan halaman: panel navy utuh, inset dan jarak tombol konsisten,
ikon 32 px, label 10 px, serta warna biru aktif yang sama. Tab Master Template
lebih lebar mengikuti proporsi referensi. Warna latar canvas dan bingkai panel
juga disamakan antara Dashboard dan halaman lain.

Efek hover dan fokus memakai aturan yang sama; fokus keyboard ditandai garis
halus tanpa mengubah warna dasar. Area klik sesuai tombol dan pilihan aktif
kembali benar ketika halaman dibuka ulang. Posisi kontrol Qt Designer dan
`build_assets.py` disesuaikan dengan geometri navigasi bersama.

Lihat `docs/navigation_all_pages.png` untuk perbandingan delapan halaman.
Pengujian pada revisi navigasi: **21 tes lulus**, termasuk kesamaan render seluruh bar untuk
pilihan menu yang sama, warna aktif/nonaktif, posisi klik, dan navigasi bolak-balik.
Pemeriksaan berjalan di Linux / PySide6 6.8.3; pengujian langsung Windows belum
dijalankan pada lingkungan ini.

## Revisi tipografi dan alignment

- Font utama **Segoe UI** bila tersedia (Windows); fallback Inter, Noto Sans,
  atau DejaVu Sans mengikuti font yang terpasang. Font sistem tidak disertakan ulang.
- Antialiasing aktif; huruf tidak lagi dipadatkan atau diregangkan secara horizontal.
- Label, angka, judul, isian, dropdown, dan tabel dirapikan pada delapan halaman.
- Area klik pada tombol Revisi dan Template mengikuti posisi tombol yang terlihat.
- Deskripsi panjang dapat membungkus; nilai dinamis yang melebihi ruang tampil
  menggunakan elipsis. Nilai lengkap tetap tersimpan; isian dapat digeser dan
  dropdown menyediakan tooltip nilai lengkap.
- Gambar tampilan terbaru ada pada `docs/dashboard_preview.png`,
  `docs/pages_contact.png`, dan `docs/previews/`.
- Pengujian: 19 tes lulus; pemeriksaan layout dan empat ukuran jendela dicatat
  pada `docs/VALIDASI_TIPOGRAFI.md`.

## Pembaruan untuk Python 3.14

Jika paket sebelumnya gagal memasang PySide6 6.8.3, ikuti
`PERBAIKAN_PYTHON_314.md`. Launcher sekarang mendeteksi versi Python dan
memasang PySide6 yang sesuai, termasuk pada `.venv` dari percobaan sebelumnya.

## Menjalankan di Windows

1. Ekstrak seluruh ZIP ke satu folder.
2. Pastikan Python **3.10–3.14, 64-bit** terpasang.
3. Klik dua kali **JALANKAN_AGREGASI.bat**.
4. Saat pertama dijalankan, launcher membuat `.venv` dan memilih dependensi otomatis:
   Python 3.10–3.13 → PySide6 6.8.3; Python 3.14 → PySide6 6.10.3.
   Koneksi internet dibutuhkan untuk pemasangan awal.
5. Sesudah dependensi terpasang, dashboard dan data lokal dapat dipakai offline.

Paket ini berisi source lengkap dan launcher; **bukan executable `.exe`**.

Manual:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python main.py
```

Linux/macOS: `bash JALANKAN_AGREGASI.sh`. Pada Linux, runtime Qt memerlukan
library sistem EGL/OpenGL dan dependensi platform desktop yang sesuai distro.

## Kontrol yang aktif

| Elemen | Perilaku |
| --- | --- |
| KPI unit dan persentase / ringkasan kanan | Membuka halaman Revisi untuk penelusuran data |
| KPI box, carton, pallet | Membuka aktivitas terfilter per tahap |
| Kartu tahap, aksi cepat, navigasi tahap | Membuka operasi scan tahap terkait |
| Monitoring dan produk aktif | Membuka halaman Pengaturan untuk konfigurasi produk dan line |
| Progress tiap tahap | Menampilkan aktivitas tahap |
| Filter grafik | Shift ini / hari ini (contoh), sesi lokal (jumlah scan tersimpan) |
| Area grafik | Menampilkan data grafik dalam tabel |
| Total valid / reject / duplikat | Membuka riwayat terfilter status |
| Tabel aktivitas utama / kanan | Membuka halaman Revisi dengan tabel, filter, detail, dan traceability |
| Perangkat dan shortcut koneksi | Membuka halaman Pengaturan perangkat |
| Upload instan | Membuka halaman Kirim Data untuk antrean sinkronisasi |
| Revision | Halaman internal untuk catatan, status, dan jejak audit |
| Kirim data | Halaman internal antrean, status sinkronisasi, riwayat, dan aksi kirim |
| Pengaturan | Halaman internal line, API, printer, scanner, kamera, user, backup |
| Master Template | Halaman internal form, canvas label, daftar, preview, dan publish |
| Logout / akun / informasi sistem | Membuka Pengaturan lokal; tidak membuat dialog modal |

**F11** layar penuh · **Esc** keluar layar penuh · **F5** segarkan ·
**Ctrl+1/2/3** membuka tahap box/carton/pallet. Tombol bisa dicapai dengan Tab;
Enter pada kolom scan menyimpan satu aktivitas.

## Mencoba agregasi

1. Buka Tahap 3, pilih **Kode contoh**, lalu **SCAN / ENTER** untuk mendaftarkan pallet.
2. Buka Tahap 2 dan daftarkan carton. Di **Hubungan kemasan**, pilih carton dan pallet
   yang valid, lalu **Hubungkan kemasan**.
3. Buka Tahap 1 dan daftarkan box. Pilih box dan carton induknya, lalu hubungkan.
4. Scan kode yang sama lagi: hasil **DUPLIKAT**, kemasan valid tidak digandakan.
5. Kode salah prefix dicatat **REJECT**. Kode kosong tidak disimpan.
6. Kode induk dan anak wajib ada, valid, dan satu batch. Kemasan anak tidak bisa
   ditautkan dua kali. Penggantian batch mengosongkan indikator kemasan saat ini.

Tahap 1 menerima kode kemasan `BOX-...`, tahap 2 `CTN-...`, tahap 3 `PLT-...`.
Nomor unit individual, aturan kapasitas isi, format GS1, dan aturan produksi
spesifik belum ditentukan oleh gambar dashboard ini. Cetak label tersedia dari
Master Template dan sesi agregasi lokal yang memakai template tersimpan.
Pemicu Max sudah menjalankan jalur auto print; perangkat scan produksi belum dihubungkan.

## Data awal dan batas integrasi

- **SIM** di panel kanan menandai mode simulasi lokal.
- Unit 18.450; valid 17.120; reject 1.330; duplikat 650; serta grafik awal adalah
  **snapshot contoh** untuk menyamakan tampilan referensi, bukan produksi langsung.
- Snapshot tahap box menampilkan total 256, valid 210, reject 18, duplikat 10 sesuai
  sumber. Selisih 18 pada sumber tidak diasumsikan termasuk kategori tertentu.
- Tabel awal memuat delapan aktivitas contoh bertanda `reference`. Pemindaian baru
  menambah statistik **kemasan**, bukan angka unit yang belum diketahui isinya.
- Grafik **SESI LOKAL** menghitung aktivitas lokal dan impor per interval dua jam
  dari seluruh data lokal tersimpan. Grafik lainnya merupakan contoh visual.
- Duplikat merupakan indikator terpisah pada snapshot unit dan bukan angka yang
  harus ditambahkan ke total unit valid + reject.
- Relasi box → carton → pallet tersimpan di tabel `packages` dan ikut ekspor JSON.
- Pengaturan memeriksa SQLite, endpoint HTTP, driver printer, port scanner dan
  kamera berdasarkan respons nyata. Panel operasi lama masih memiliki snapshot
  referensi. Master Template memakai daftar printer OS dan dialog cetak sistem.
- Akun lokal belum autentikasi produksi. Kirim Data menggunakan antrean HTTP
  yang hanya ditandai SUCCESS setelah server memberikan pengakuan JSON.
  Baca kontrak API dalam Panduan Pengaturan sebelum menghubungkan server.
- Backend produksi C#/Supabase, SDK optik perangkat industri dan autentikasi
  belum dikonfigurasi. Adapter HTTP/serial/driver/ZPL tersedia sesuai panduan.
  Paket ini tidak menimpa source Scode_v1 atau backend sebelumnya.

## Penyimpanan

Data dan konfigurasi disimpan otomatis di lokasi aplikasi OS melalui
`QStandardPaths.AppLocalDataLocation`, di bawah organisasi `AGREGASI` dan aplikasi
`AGREGASI_UI`. Lokasi tepat dapat dilihat lewat **Informasi Sistem**. Untuk
penyimpanan portabel gunakan:

```bash
python main.py --data-dir ./data
```

Jangan mengganti file database saat aplikasi sedang berjalan. Untuk pencadangan,
tutup aplikasi, lalu salin file `agregasi.sqlite3`. Ekspor JSON dapat dilakukan
selagi aplikasi terbuka.

## Struktur yang siap dilanjutkan

- `runtime_check.py` — pemeriksaan Python, arsitektur, dan versi dependensi.
- `main.py` — entry point, konfigurasi direktori data, mode screenshot.
- `agregasi/app.py` — shell responsif, stacked pages, dan navigasi internal.
- `agregasi/dashboard.py` — render panel, teks, progress, grafik, dan indikator.
- `agregasi/pages.py` — halaman Box, Carton, Pallet, Revisi, Kirim Data,
  dan Pengaturan.
- `agregasi/template_page.py` / `template_workspace.py` — tiga editor template.
- `agregasi/template_model.py` — dokumen label, validasi, CRUD dan publikasi SQLite.
- `agregasi/label_canvas.py` — interaksi canvas, penggaris, grid dan undo/redo.
- `agregasi/label_render.py` — encoder kode dan renderer label, PNG, PDF, printer.
- `agregasi/editor_icons.py` — ikon vektor selector, toolbar dan toolbox.
- `agregasi/dialogs.py` — operasi tahap, riwayat, pengaturan, perangkat, impor/ekspor.
- `agregasi/store.py` — SQLite, validasi scan, relasi kemasan, dan jejak audit.
- `ui/dashboard.ui` — 46 kontrol dashboard interaktif, bisa dibuka di **Qt Designer**.
- `assets/svg/` — ikon vektor yang dapat diedit.
- `styles/theme.qss` — gaya dialog dan kontrol.
- `build_assets.py` — pembangkit SVG dan kontrol `.ui`; regenerasi akan menimpa
  modifikasi manual pada file yang dihasilkan, jadi gunakan hanya bila diperlukan.
- `tests/` — pengujian penyimpanan, validasi, impor, navigasi, dan skala.
- `docs/dashboard_preview.png` — tangkapan layar render aplikasi yang diuji.

File `.ui` mengatur overlay kontrol; panel visual digambar di `dashboard.py`.
Menyesuaikan posisi tombol di Designer perlu disertai penyesuaian posisi visual
terkait di dashboard. Ikon SVG bukan tracing piksel, sehingga detail garis dan
font dapat sedikit berbeda dari gambar asli, terutama antar sistem operasi.

Halaman berikutnya dapat diganti melalui `MainWindow.register_page(stage, factory)`
tanpa mengubah model data atau tombol dashboard. Setiap page memakai canvas Qt
yang sama sehingga tombol navigasi tetap konsisten pada ukuran layar berbeda.

## Pengujian

```bash
python -m unittest discover -s tests -v
```

Screenshot untuk QA:

```bash
python main.py --data-dir ./qa_data --screenshot ./dashboard.png
```

Hasil editor terbaru ada di `docs/VALIDASI_TEMPLATE.md`; laporan revisi lama
dipertahankan di `docs/VALIDASI.md` dan berkas validasi lain.
