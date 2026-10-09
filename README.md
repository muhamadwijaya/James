# James — pm3tool

Wrapper Python sederhana untuk **Proxmark3** (firmware **Iceman/RRG**) yang
memudahkan:

- membaca berbagai jenis kartu RFID (LF 125 kHz & HF 13.56 MHz),
- menampilkan datanya (UID, ATQA, SAK, EM410x ID),
- **memulihkan key MIFARE Classic pada kartu milik Anda sendiri** yang
  kuncinya lupa, lalu men-dump isinya.

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

Setelah `pm3` ada, di GUI klik **Browse…** di sebelah kolom *Binary* dan
arahkan ke `pm3`/`pm3.bat`/`pm3.exe` (atau isi `pm3` jika sudah di PATH).

## Pemakaian — GUI (tampilan grafis)

GUI utama memakai **PySide6 (Qt)**.

**Cara termudah — tinggal dobel-klik:**
- **Windows:** `run.bat` (otomatis cek Python, pasang PySide6, lalu buka GUI).
- **Linux/macOS:** `./run.sh`.

**Manual:**
```bash
pip install PySide6        # sekali saja
python -m pm3tool gui      # atau: python -m pm3tool.gui_qt
```

Jendela punya kolom **Binary**/**Port** di atas dan dua tab:

- **Reader** — tombol **Check**, **Scan (LF+HF)**, **Read HF**, **Read LF**,
  **Recover Keys**, **Dump…**.
- **Dump Viewer** — lihat isi file dump (.bin/.eml/.json) per blok dalam
  **hex + ASCII**, filter per sektor (mis. `1-4`), trailer diurai
  (KeyA / AC+GPB / KeyB). Berguna membandingkan data teks vs hex mentah.
- **Clone** — pindahkan isi kartu ke chip baru: deteksi kartu magic,
  clone ke magic Gen1a (`hf mf cload`), restore pakai key
  (`hf mf restore`), set UID magic (`hf mf csetuid`), wipe & verify.
- **Firmware** — **Temukan firmware**, **Flash ALL**, **Flash fullimage**,
  **Flash bootrom**, flash file `.elf` kustom, dan **Download & build
  firmware** dari source resmi Iceman.

Hasil tampil di log hitam di bawah. Operasi panjang (hardnested, flash,
build) berjalan di thread terpisah sehingga jendela tetap responsif.

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
