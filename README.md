# James — pm3tool

Wrapper Python sederhana untuk **Proxmark3** (firmware **Iceman/RRG**) yang
memudahkan:

- membaca berbagai jenis kartu RFID (LF 125 kHz & HF 13.56 MHz),
- menampilkan datanya (UID, ATQA, SAK, EM410x ID),
- **memulihkan key MIFARE Classic pada kartu milik Anda sendiri** yang
  kuncinya lupa, lalu men-dump isinya,
- **mengisi chip ink baru kosong** dengan data dan key dari dump chip
  belum terpakai, dengan kode BK/tanggal yang dapat diisi, preview, backup,
  dan verifikasi pembacaan balik.

Tool ini **tidak** berisi firmware atau kode kriptografi sendiri. Ia hanya
menjalankan perintah client `pm3` resmi (`hf search`, `lf search`,
`hf mf autopwn`, `hf mf dump`, dll.) dan merapikan outputnya. Semua
kemampuan pemulihan key berasal dari firmware Iceman.

## Prasyarat

1. Perangkat **Proxmark3** + antena.
2. **WAJIB: client Proxmark3 (`pm3` / `pm3.exe` / `pm3.bat`) sudah terpasang.**
   pm3tool hanya *memanggil* client ini — tanpa `pm3`, tidak ada yang jalan.
   Catatan: COM port yang muncul di Windows **belum** berarti client ada.
3. Python 3.10+.

### Memasang client `pm3`

- **Windows (disarankan: ProxSpace):**
  1. Unduh **ProxSpace**: <https://github.com/Gator96100/ProxSpace> → Releases.
  2. Ekstrak ke path pendek tanpa spasi, mis. `C:\ProxSpace`.
  3. Jalankan `runme64.bat` → terminal ProxSpace terbuka.
  4. Build client + firmware:
     ```
     git clone https://github.com/RfidResearchGroup/proxmark3.git
     cd proxmark3
     make clean && make -j
     ```
     Menghasilkan `pm3` (client) + `bootrom.elf`/`fullimage.elf` (firmware).
  5. Flash: `pm3-flash-all`. Tes: `pm3 -p com10`.
- **Linux/macOS:** ikuti <https://github.com/RfidResearchGroup/proxmark3>
  (`make clean && make -j && sudo make install`).

Setelah client selesai dibangun, aplikasi otomatis mencari `proxmark3.exe`
di `C:\ProxSpace\pm3\proxmark3\client`, `client\build`, folder repo, dan PATH.
Instalasi di lokasi lain dapat dipilih melalui **Browse…** atau dengan
mengisi kolom **PM3** memakai path file/folder.

## Pemakaian — GUI (tampilan grafis)

GUI utama memakai **PySide6 (Qt)**.

**Cara termudah — tinggal dobel-klik:**
- **Windows + ProxSpace (disarankan): `run_pm3.bat`.** Otomatis menemukan
  `proxmark3.exe` milik ProxSpace, menambahkan lokasi DLL saat client
  dijalankan, dan mendeteksi port USB Proxmark3. Nomor COM tidak dikunci.
  Lokasi awal pencarian adalah `C:\ProxSpace\pm3\proxmark3`; lokasi lain
  dapat ditentukan melalui Browse atau variabel lingkungan `PM3_ROOT`.
  Catatan: tutup dulu sesi interaktif `pm3 -->` bila terbuka (satu COM port
  hanya untuk satu program).
- **Windows:** `run.bat` memakai deteksi otomatis yang sama.
- **Linux/macOS:** `./run.sh`.

> Saat GUI dibuka, kolom PM3 dan Port diisi dari hasil deteksi. Pilihan
> manual melalui `PM3_BINARY`, `PM3_PORT`, `--binary`, atau `--port` tetap
> digunakan. Tombol **Auto Detect** mengulang pencarian dan kembali ke
> mode otomatis, termasuk setelah USB dicabut lalu dipasang kembali.

Port PM3 dikenali dari identitas USB atau nama Proxmark3. Jika terdapat
lebih dari satu PM3, log menampilkan daftar port dan Anda perlu memilih
salah satunya. Port perangkat serial lain tidak dipilih otomatis. Deteksi
Windows memakai PowerShell bawaan tanpa dependensi serial tambahan;
`pyserial`, bila tersedia, juga digunakan untuk enumerasi port.

Untuk memeriksa deteksi tanpa membuka koneksi perangkat:

```bash
python -m pm3tool detect
```

**Manual:**
```bash
pip install PySide6        # sekali saja
python -m pm3tool gui      # atau: python -m pm3tool.gui_qt
```

Jendela punya kolom **PM3**/**Port**, tombol **Auto Detect**, dan tujuh tab:

- **Reader** — tombol **Check**, **Scan (LF+HF)**, **Read HF**, **Read LF**,
  **Recover Keys**, **Dump…**.
- **Dump Viewer** — lihat isi file dump (.bin/.eml/.json) per blok dalam
  **hex + ASCII**, filter per sektor (mis. `1-4`), trailer diurai
  (KeyA / AC+GPB / KeyB). Berguna membandingkan data teks vs hex mentah.
- **Clone** — pindahkan isi kartu ke chip baru: deteksi kartu magic,
  clone ke magic Gen1a (`hf mf cload`), restore pakai key
  (`hf mf restore`), set UID magic (`hf mf csetuid`), wipe & verify.
- **Write Data / Recycle** — salin data dari chip belum terpakai, profil opsional, dengan
  preview, backup kartu terpasang, pemeriksaan UID, dan pembacaan ulang.
- **Firmware** — **Temukan firmware**, **Flash ALL**, **Flash fullimage**,
  **Flash bootrom**, flash file `.elf` kustom, dan **Download & build
  firmware** dari source resmi Iceman.
- **Recovery Keys** — pusat recovery dengan metode kartu, reader attack,
  analisis trace, script, dan tool nonce offline; output langsung dan log per sesi.
- **Write Chip Ink Baru** — entry otomatis dari acuan belum terpakai,
  kode BK/tanggal kustom, salin data dan key ke chip kosong, lalu baca ulang.

Hasil tampil di log hitam di bawah. Operasi panjang (hardnested, flash,
build) berjalan di thread terpisah sehingga jendela tetap responsif.

## Write Chip Ink Baru

1. Buka **Write Chip Ink Baru**. Pilih acuan **BKA236T — C2A4DA95** atau
   **BKA236T — D2E2DC95**, atau pilih dump lengkap chip belum terpakai sendiri.
   Kode BK, tanggal, ASCII, seluruh 64 blok HEX, dan Key A/B terisi otomatis.
2. Isi **Kode BK / produk** (misalnya `BKA236T`) dan pilih **Tanggal chip**
   dalam format `DD/MM/YYYY`. Kalender dan input tanggal tersedia. Kolom
   **Tanggal YYMMDD** serta HEX/ASCII berubah langsung mengikuti isian.
   Jika isian dibiarkan seperti acuan, seluruh data tetap persis seperti acuan.
3. Tempelkan **chip baru kosong** pada antena. Pilih mode sesuai chip, lalu
   klik **1. Baca chip kosong + Preview**. Backup dibuat dan daftar blok
   yang akan ditulis ditampilkan. Belum ada penulisan pada tahap ini.
4. Klik **2. Write Chip Baru**, kemudian tunggu sampai **TERVERIFIKASI**.
   Data ditulis dan dibaca ulang sebelum key sektor diubah. Key baru juga
   diuji lewat autentikasi dan pembacaan trailer. Dump akhir dibandingkan
   dengan hasil yang diharapkan.

| Mode | Hasil | Chip target |
|---|---|---|
| Chip biasa | Blok 1–63 mengikuti data pada form, termasuk kode/tanggal yang diisi. Key A/B dan AC/GPB mengikuti acuan. Blok 0/UID chip baru dipertahankan. | MIFARE Classic 1K, UID 4 byte, SAK 08 |
| Magic Gen1a | Seluruh 1.024 byte / 64 blok mengikuti data pada form, termasuk blok 0 dan UID acuan. Blok 0 ditulis terakhir. | Chip Magic Gen1a kosong yang mendukung `cgetblk` / `csetblk` |

Pemeriksaan chip kosong mensyaratkan semua blok data selain blok 0 bernilai
`00`, Key A/B awal `FFFFFFFFFFFF`, dan access bits transport `FF0780` di
seluruh sektor. Target berisi data, mode Gen1a pada chip biasa, UID berbeda
dari preview, atau backup yang berubah akan menghentikan proses. Acuan
juga harus dump 1K lengkap dengan access bits `FF0780` di seluruh sektor.
Sumber BIN/EML/JSON didukung; file key sumber diperoleh dari trailer dump.

Acuan bawaan disalin persis dari dua dump chip **belum terpakai** yang
dikirim pengguna. Kedua kode produknya `BKA236T`, teks tanggalnya `260321`,
Key A/B sektor 1, 3, 4 `436F44506144`, key sektor lainnya `FFFFFFFFFFFF`,
dan AC/GPB `FF078069`. Manifest SHA-256 dan dump/key disertakan di
`pm3tool/ink_references/`. Acuan bawaan tidak diubah oleh pengisian form;
personalisasi menghasilkan data baru di memori. Tombol **Simpan data + key…**
mengekspor dump hasil isian beserta file key PM3 192 byte. Tidak perlu
mengisi profil JSON untuk fitur ini.

### Pengisian kode BK dan tanggal

Kode mendukung 1–7 huruf kapital `A–Z` atau angka `0–9`. Kode yang lebih
pendek diisi dengan byte `00` sampai tujuh posisi. Tanggal mendukung tahun
2000–2099 dan divalidasi oleh kalender, termasuk tanggal kabisat. Format
yang diedit dikenali dari susunan data CoDPaD pada acuan; tanggal ASCII dan
biner acuan harus cocok. Acuan dengan format lain tetap bisa disalin tanpa
personalisasi.

| Isian | Letak dalam dump | Contoh: `BKA236T`, 10 Oktober 2026 |
|---|---|---|
| Kode BK / produk | Blok 4 byte 0–6 | `42 4B 41 32 33 36 54` |
| Tahun dan bulan biner | Blok 4 byte 14–15 | `1A 0A` (26, 10 desimal) |
| Hari biner | Blok 5 byte 0 | `0A` (10 desimal) |
| Tanggal ASCII `YYMMDD` | Blok 5 byte 1–6 | `261010`, HEX `32 36 31 30 31 30` |

Nomor byte dimulai dari 0. Tahun biner adalah tahun dikurangi 2000, bukan
angka BCD. Jenis tanggal belum ditetapkan sebagai produksi, pengisian,
atau kedaluwarsa; isian mengikuti field tanggal pada acuan. Jika sektor 2
sudah merupakan salinan data sektor 1, kode/tanggal pada blok 8–9 ikut
disinkronkan. Sektor 2 yang kosong tetap kosong. Setiap perubahan kode,
tanggal, mode, atau folder membatalkan preview lama; buat Preview kembali.

**Batas personalisasi:** byte yang belum diketahui fungsinya, termasuk
blok 6 dan sektor 3/4, tetap mengikuti chip sumber. Software tidak menebak
atau menghitung ulang CRC, MAC, atau data autentikasi aplikasi. Key seluruh
sektor mengikuti acuan. Pengisian kode/tanggal dan verifikasi pembacaan
balik tidak membuktikan penerimaan oleh printer. Jika printer memeriksa
hubungan kode/tanggal dengan field validasi tersebut, diperlukan susunan
data valid yang sesuai agar chip diterima.

Mengubah kode menjadi produk lain tidak mengubah kapasitas atau parameter
produk lainnya. Untuk produk lain seperti `WTA252T`, gunakan acuan belum
terpakai dari produk tersebut. ASCII hanya tampilan: titik berarti byte
non-ASCII, bukan byte yang dihapus atau diganti saat menulis.

Setiap sesi menyimpan `before.bin`, `before-key.bin`, `reference.bin`,
`reference-key.bin`, `expected.bin`, `preview.json`, `preflight.bin`,
`journal.json`, `session.log`, serta `after.bin` jika dump akhir selesai.
Kode/tanggal kustom dan SHA-256 acuan asal dicatat pada `preview.json`
serta `journal.json`; status penerimaan printer dicatat `not_verified`.
**Hentikan** berhenti setelah perintah PM3 aktif selesai. Proses yang
terhenti dapat meninggalkan sebagian blok/key sudah berubah; journal
menyebutkan blok terverifikasi dan blok yang sedang ditulis. Status sukses
hanya diberikan setelah verifikasi lengkap. Satu preview dipakai sekali.

Pengujian software menggunakan simulator yang memeriksa autentikasi key,
perubahan UID, kegagalan tulis, pembacaan balik, dan klik GUI. Perangkat
PM3/chip fisik dan penerimaan oleh mesin ink belum diuji di lingkungan ini.
Data aplikasi dapat terkait UID; penyalinan ke chip biasa belum menjamin
mesin menerima UID berbeda. Mode Gen1a menyalin seluruh dump termasuk
UID acuan, dengan personalisasi jika dipilih.

Perintah mengikuti dokumentasi resmi RRG:
[daftar perintah](https://github.com/RfidResearchGroup/proxmark3/blob/master/doc/commands.md),
[cheatsheet](https://github.com/RfidResearchGroup/proxmark3/blob/master/doc/cheatsheet.md),
dan [jenis kartu magic](https://github.com/RfidResearchGroup/proxmark3/blob/master/doc/magic_cards_notes.md).

## Recovery Keys

Tab ini menyediakan 31 pilihan recovery, diagnostik, persiapan emulator,
script, dan tool offline. Kelompok recovery MIFARE Classic resmi RRG:
`autopwn`, `fchk`, `chk`, `darkside`, `nested`, `hardnested`, `staticnested`,
`sen`, `brute`, `nack`, `decrypt`, `supercard`, dan `keygen`.
Tidak semua pilihan adalah algoritme pemecahan key: NACK/INFO/ISEN adalah
diagnostik; keygen menghasilkan kandidat KDF untuk diuji, bukan key terverifikasi.

Tambahan: `hf mf info`, `hf mf isen`, pengumpulan nonce FM11RF08S, reader
attack biasa/nested (`hf mf sim -x/-y`), sniff lalu trace, analisis trace,
`script run fm11rf08s_recovery.py`, script lain yang terpasang, muat emulator,
dan tampilan key emulator. Opsi reader lain, termasuk opsi yang tersedia
pada build tertentu, bisa dimasukkan melalui **Parameter tambahan** atau
kolom perintah. **Help metode** membaca bantuan langsung dari client.

Tool offline: `mfkey32`, `mfkey32v2`, `mfkey64`, `nonce2key`,
`staticnested_1nt`, `staticnested_2x1nt_rf08s`, dan
`staticnested_2x1nt_rf08s_1key`. Executable/script tidak disertakan dalam ZIP
wrapper: gunakan tool dari instalasi Proxmark3. Aplikasi mencari executable
di PATH dan direktori instalasi; lokasi lain bisa dipilih. Script FM11RF08S
memerlukan dukungan Python PM3 dan tool pendukung yang sesuai.

Recovery satu klik (chip 1K pada contoh pengguna):

1. Tempelkan kartu pada antena PM3.
2. Klik **Recover Keys (dari kartu)** pada tab Reader, atau **Recover otomatis**
   pada tab Recovery Keys.
3. Tunggu. Output proses dan waktu berjalan tampil langsung; tabel key dan
   lokasi hasil ditampilkan otomatis saat selesai.

Tombol ini langsung menjalankan `hf mf autopwn` tanpa pemeriksaan Help
sebelumnya. PM3 menjalankan dictionary dan memilih serangan sesuai kartu.
Isian metode lanjutan, mode offline, UID, dan parameter lama tidak memengaruhi
tombol otomatis. Batas waktu otomatis 120 menit. Direktori kerja PM3 tetap
folder aplikasi sehingga lokasi resource tidak berubah. **Hentikan** dapat
membatalkan proses. Kegagalan ditampilkan beserta penyebabnya, dan tombol
diaktifkan kembali untuk mencoba ulang.

Centang **Metode lanjutan (opsional)** bila ingin menjalankan metode tersendiri,
menggunakan file nonce/reader, atau memilih ukuran kartu selain 1K. Semua
metode sebelumnya tetap tersedia. Alur lanjutan:

1. Pilih **Diagnostik kartu / PRNG** untuk memeriksa jenis kartu, atau mulai
   dengan **Autopwn** untuk pemilihan serangan otomatis bawaan PM3.
2. Pilih metode lain sesuai data yang tersedia. Nested/staticnested perlu
   satu key valid; hardnested memerlukan parameter blok/target atau file
   nonce offline. Reader attack memerlukan transaksi reader, dan nested
   reader attack memerlukan nt/nt_enc yang sudah dimuat pada emulator.
3. Isi ukuran kartu, key/blok/tipe yang diketahui, UID, dictionary, atau
   file nonce. Gunakan Help untuk parameter khusus. Kolom yang tidak digunakan
   oleh metode tersebut diabaikan.
4. Klik **Susun perintah** dan periksa perintah. **Jalankan metode pilihan** juga
   menyusun ulang perintah dari kolom terbaru, kecuali kolom perintah diedit
   langsung. Perintah boleh diedit untuk semua opsi metode terpilih.
5. Batas waktu bawaan 120 menit per proses, dapat dinaikkan. Output tampil
   langsung. **Hentikan** membatalkan proses client dan proses anaknya;
   untuk mengakhiri simulasi/sniff perangkat, tekan tombol PM3 bila perlu.
6. **Metode dari PM3** menambahkan command baru di bagian recovery client
   terpasang. **Daftar script** menampilkan script yang tersedia. Metode
   dapat diperiksa melalui **Help metode** bila diperlukan. Help bukan
   syarat menjalankan recovery; command yang tidak tersedia dilaporkan dari
   hasil eksekusi sebenarnya.

Setiap sesi menyimpan `session.log`, `report.json`, dan `recovered.dic`.
Dictionary berisi key unik yang ditemukan, untuk pemeriksaan FCHK/CHK
berikutnya. Laporan memisahkan key bernomor sektor, key tanpa informasi
sektor, dan pasangan sektor A/B yang belum ditemukan untuk ukuran terpilih.
SEN/script FM11RF08S 1K juga melaporkan key sektor ekstra 32 secara terpisah.
Log Help serta key input tidak dihitung sebagai hasil recovery. Status
`keys_found` tidak berarti seluruh key sudah ditemukan; `no_keys`, `failed`,
`timeout`, dan `cancelled` dicatat tersendiri. Key reader/nonce offline perlu
diuji pada kartu dengan UID yang sesuai. File key/dump dari command PM3
tetap mengikuti lokasi yang ditampilkan client di log.

CLI:

```bash
python -m pm3tool recovery-methods
python -m pm3tool recovery-run autopwn --params="--1k" --minutes 120
python -m pm3tool recovery-run sen --minutes 180
python -m pm3tool recovery-run hardnested --offline --params="-r -f nonces.bin" --minutes 180
```

Tidak ada metode yang menjamin recovery untuk semua kartu. Smart brute
force menguji pola key lemah; penambahan metode tidak menghapus persyaratan
nonce, key awal, atau transaksi reader. Sumber metode resmi:
https://github.com/RfidResearchGroup/proxmark3/blob/master/doc/commands.md

## Write Data / Recycle

Fitur ini mendukung MIFARE Classic-kompatibel 1K dengan UID 4 byte.
Gunakan key yang cocok dengan chip target dan blok data yang mengizinkan
penulisan. Dump chip belum terpakai dapat dipilih sebagai acuan langsung,
tanpa file profil JSON. Semua 47 blok data biasa mengikuti acuan; hanya
blok yang berbeda dari target akan ditulis.

UID/blok 0 dan seluruh sector trailer (key/access bits) target dipertahankan,
termasuk bila berbeda dari acuan. Profil khusus opsional dapat membatasi
penyalinan ke blok atau byte tertentu. Fitur ini memverifikasi kesesuaian
byte hasil tulis; pengujian pada mesin menentukan apakah chip dapat digunakan
kembali. Menyalin data antar-UID tidak membuktikan reset aplikasi: data yang
terikat UID atau MAC/checksum tidak dihitung ulang oleh fitur ini. Reset
key/access bits atau UID tidak termasuk pada alur Recycle ini.

Alur GUI Qt:

1. Siapkan dump dan key file terbaru dari chip target, serta dump chip belum terpakai.
2. Pada tab **Write Data / Recycle**, pilih **Data acuan**, **Backup chip target**,
   dan **Key chip target**. Biarkan **Profil khusus (opsional)** kosong untuk
   menyalin semua blok data biasa dari acuan.
3. Jika ingin memilih bagian tertentu, **Buat profil dari daftar blok…** dapat
   membuat profil dari dump acuan. Untuk memilih sebagian byte, gunakan mask
   profil: `FF` menyalin byte acuan, `00` mempertahankan byte target.
4. Klik **Preview perubahan** dan periksa UID, blok, serta data sebelum/sesudah.
5. Tempel satu chip target, pilih folder hasil, lalu **Write Data…**.
6. Aplikasi membuat backup live lengkap, memeriksa kecocokan dengan dump
   target, menulis blok pilihan, dan memverifikasi hasil per blok serta dump akhir.
7. Setelah data terverifikasi, uji chip pada mesin pabrikan.

Preview CLI tanpa profil (tidak mengakses kartu):

```bash
python -m pm3tool recycle --reference acuan.bin --target target.bin --keyfile target-key.bin
```

Profil opsional untuk menyalin hanya blok yang dipilih (nomor berikut ilustratif):

```bash
python -m pm3tool recycle-profile --reference acuan.bin --blocks 1-2 --output profil.json
python -m pm3tool recycle --reference acuan.bin --target target.bin --keyfile target-key.bin --profile profil.json
```

Perintah kedua hanya preview dan tidak mengakses kartu. Setelah memeriksa
preview, tambahkan `--apply --confirm-uid <UID_TARGET>` untuk menulis.
Profil khusus menyimpan SHA-256 data acuan, sehingga mengganti acuan memerlukan
profil yang cocok. Nomor byte pada mask dimulai dari 0 sampai 15 per blok.

Folder hasil memiliki subfolder unik per eksekusi yang berisi `before.bin`,
`target-key.bin`, `expected.bin`, `after.bin` jika verifikasi lengkap selesai,
dan `journal.json`. Proses beberapa blok tidak atomik: jika penulisan atau
verifikasi gagal, operasi berhenti dan status `incomplete` dicatat. Backup
tetap tersedia; rollback tidak dijalankan otomatis. `aborted_before_write`
berarti operasi berhenti sebelum mengirim perintah tulis.

Key file PM3 berukuran 192 byte maupun 204 byte (tambahan entri sektor
FM11RF08S) didukung untuk autentikasi 16 sektor utama. Parser pemulihan key
juga mendukung tabel modern `Sec | Blk | key A | res | key B | res`.

Rujukan teknis: [tata memori dan akses MIFARE Classic](https://www.nxp.com/docs/en/data-sheet/MF1S50YYX_V1.pdf)
dan [perintah resmi PM3](https://github.com/RfidResearchGroup/proxmark3/blob/master/doc/cheatsheet.md).

Masih tersedia GUI ringan berbasis Tkinter:

```bash
python -m pm3tool gui-tk
```

(Tkinter bawaan installer Python di Windows/macOS; di Linux pasang
`python3-tk`.)

## Firmware & flashing

Firmware Proxmark3 bersifat open-source (GPL) dan berasal dari repo resmi
**Iceman/RRG** (<https://github.com/RfidResearchGroup/proxmark3>). Tool ini
**tidak** menyertakan biner firmware; ia hanya:

- **membangun** firmware dari source (`Firmware ▸ Download & build`, butuh
  `git`, `make`, dan toolchain `arm-none-eabi-gcc`), atau
- **menemukan** `bootrom.elf`/`fullimage.elf` yang sudah terpasang, lalu
- **flash** lewat tool resmi: `pm3-flash-all`, `pm3-flash-fullimage`,
  `pm3-flash-bootrom`, atau `flasher` mentah dengan file `.elf` pilihan.

> Flash hanya perangkat Proxmark3 milik Anda. Jangan cabut saat proses
> berlangsung. Jika bootrom gagal, tahan tombol perangkat saat mencolok
> untuk masuk mode bootloader, lalu ulangi.

## Pemakaian — CLI

```bash
# cek koneksi & tuning antena
python -m pm3tool check

# deteksi otomatis kartu (LF + HF)
python -m pm3tool scan

# baca kartu 13.56 MHz / 125 kHz
python -m pm3tool read-hf
python -m pm3tool read-lf

# pulihkan key MIFARE Classic kartu Anda (autopwn: dict + nested/hardnested)
python -m pm3tool recover-keys
python -m pm3tool recover-keys --dict daftar_key_saya.dic

# pulihkan key LEWAT READER (kalau Anda punya reader-nya)
python -m pm3tool recover-reader --uid 2CD72F90   # PM3 jadi kartu (mfkey32)
python -m pm3tool sniff                           # sadap reader↔kartu lalu crack

# dump isi kartu memakai key yang sudah ditemukan
python -m pm3tool dump --keyfile hf-mf-ABCD1234-key.bin

# lihat isi dump dalam hex + ASCII (bandingkan teks vs data mentah)
python -m pm3tool view --dump hf-mf-2CD72F90-dump.bin --sectors 1-4
python -m pm3tool view --dump d.bin --sectors 1-4 --format ascii

# clone / pindah data ke chip baru
python -m pm3tool clone --info                         # deteksi kartu magic
python -m pm3tool clone --gen1a --dump hf-mf-2CD72F90-dump.bin   # ke magic Gen1a
python -m pm3tool clone --dump d.bin --keyfile k.bin   # restore pakai key
python -m pm3tool clone --set-uid 2CD72F90             # set UID magic Gen1a
```

## Clone ke chip baru (pindah data)

Alur memindahkan isi kartu lama ke chip baru:

1. **Recover Keys** pada kartu asli → menghasilkan file dump `.bin` dan
   key `.bin` (di direktori kerja client PM3).
2. Siapkan **chip baru**. Untuk UID yang **sama**, chip harus kartu
   **magic** (Gen1a/Gen2/Gen3) — MIFARE Classic biasa mengunci blok 0
   (UID) dari pabrik, jadi UID-nya tidak bisa diubah.
3. Tulis dump ke chip baru:
   - **Magic Gen1a** → `clone --gen1a` (menulis semua blok **termasuk UID**).
   - **Kartu normal / Gen2** → `clone` (restore data pakai key; UID ikut
     hanya dengan `--block0` pada Gen2/CUID).
4. (Opsional) set UID manual dengan `--set-uid`, lalu verifikasi di GUI
   (tombol **Verifikasi**, `hf mf cview`).

Jika port tidak terdeteksi otomatis, tentukan manual:

```bash
python -m pm3tool --port /dev/ttyACM0 scan     # Linux
python -m pm3tool --port COM3 scan             # Windows
```

## Pemulihan key lewat reader

Kalau Anda masih punya **reader** yang tahu key kartu, key bisa dipulihkan
tanpa menyerang kartunya. Reader tidak pernah mengirim key (MIFARE Classic
pakai challenge-response Crypto1), tapi key bisa **dihitung** dari
autentikasinya:

- **`recover-reader`** — PM3 menyamar sebagai kartu (`hf mf sim ... -x`),
  Anda tempelkan PM3 ke reader, nonce reader dikumpulkan lalu key dihitung
  (mfkey32). Beri `--uid` sama dengan kartu asli agar reader mau berinteraksi.
- **`sniff`** — sadap transaksi reader↔kartu asli (`hf 14a sniff`) lalu
  dekode & pulihkan key dari trace (`trace list -t mf`, mfkey64).

Di GUI, keduanya ada di tab **Reader** → grup "Recover key lewat READER".
Sering lebih cepat daripada autopwn. Gunakan hanya pada reader/kartu sendiri.

## Catatan tentang `recover-keys`

Perintah ini membungkus `hf mf autopwn`, yang mencoba dictionary key umum
lalu serangan nested/hardnested yang sudah dipublikasikan untuk memulihkan
key. hardnested bisa memakan beberapa menit — jangan lepaskan kartu dari
antena selama proses berjalan. Setelah key ditemukan, autopwn otomatis
men-dump isi kartu ke file di direktori kerja client.

> Gunakan hanya pada kartu yang Anda miliki atau yang Anda punya izin untuk
> mengaksesnya.

## Test

```bash
pip install pytest
python -m pytest tests/
```

Test parser tidak membutuhkan perangkat keras.
