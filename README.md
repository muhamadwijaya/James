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
2. Client **Iceman/RRG** terpasang, dan executable `pm3` ada di `PATH`.
   Lihat <https://github.com/RfidResearchGroup/proxmark3>.
3. Python 3.10+.

## Pemakaian — GUI (tampilan grafis)

```bash
python -m pm3tool gui
# atau: python -m pm3tool.gui
```

Jendela berisi kolom **Binary**/**Port** di atas dan tombol **Check**,
**Scan (LF+HF)**, **Read HF**, **Read LF**, **Recover Keys**, **Dump…**.
Hasil tampil di area teks hitam di bawahnya. Perintah panjang (mis.
hardnested) berjalan di latar belakang sehingga jendela tetap responsif.

GUI memakai **Tkinter**, yang sudah termasuk di installer Python resmi
(Windows & macOS). Di Linux, pasang dulu paket `python3-tk`
(mis. `sudo apt install python3-tk`).

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

# dump isi kartu memakai key yang sudah ditemukan
python -m pm3tool dump --keyfile hf-mf-ABCD1234-key.bin
```

Jika port tidak terdeteksi otomatis, tentukan manual:

```bash
python -m pm3tool --port /dev/ttyACM0 scan     # Linux
python -m pm3tool --port COM3 scan             # Windows
```

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
