"""Clone / pindah data MIFARE Classic ke chip baru lewat perintah PM3.

Alur umum memindahkan isi kartu ke chip baru:

  1. Pulihkan key + dump kartu asli  -> scanner.recover_mifare_keys()
     (menghasilkan file dump .bin dan key .bin di working dir client).
  2. Siapkan chip baru. Untuk UID yang SAMA, chip harus kartu "magic"
     (Gen1a/Gen2/Gen3) karena MIFARE Classic biasa mengunci blok 0 (UID)
     dari pabrik.
  3. Tulis dump ke chip baru:
       * Gen1a (magic klasik) -> clone_to_gen1a()  (`hf mf cload`)
       * kartu normal / Gen2  -> restore_dump()     (`hf mf restore`)
     Set UID magic bila perlu -> set_magic_uid()    (`hf mf csetuid`).

Semua fungsi hanya menyusun perintah standar firmware Iceman; tidak ada
logika low-level sendiri. Gunakan hanya pada kartu/chip milik Anda.
"""

from __future__ import annotations

import re

from .client import PM3Client, PM3Result

# generasi magic yang terdeteksi dari output `hf mf info`
_MAGIC_RE = re.compile(r"(Gen\s*1a|Gen\s*2|Gen\s*3|Gen\s*4|GDM|CUID|FUID|UFUID)",
                       re.IGNORECASE)


def card_info(client: PM3Client) -> dict:
    """Deteksi jenis kartu & apakah 'magic' lewat `hf mf info`.

    Mengembalikan {magic: bool, generations: [...], raw: str}.
    """
    res = client.run("hf mf info")
    gens = sorted({m.replace(" ", "").title() for m in _MAGIC_RE.findall(res.stdout)})
    return {"magic": bool(gens), "generations": gens, "raw": res.stdout}


def clone_to_gen1a(client: PM3Client, dumpfile: str,
                   timeout: float = 120.0) -> PM3Result:
    """Tulis seluruh dump (termasuk blok 0/UID) ke kartu magic Gen1a.

    Memakai `hf mf cload -f <dump>`. File dump bisa .bin/.eml/.json
    (ekstensi boleh dihilangkan, PM3 melengkapinya).
    """
    return client.run(f"hf mf cload -f {dumpfile}", timeout=timeout)


def restore_dump(client: PM3Client, dumpfile: str | None = None,
                 keyfile: str | None = None, write_block0: bool = False,
                 timeout: float = 120.0) -> PM3Result:
    """Tulis dump ke kartu memakai key (kartu normal / magic Gen2).

    `hf mf restore` menulis blok data per sektor memakai key dari
    `keyfile`. Blok 0 (UID) hanya ditulis bila `write_block0=True`
    (butuh kartu yang mengizinkan, mis. Gen2/CUID).
    """
    cmd = "hf mf restore --1k"
    if dumpfile:
        cmd += f" -f {dumpfile}"
    if keyfile:
        cmd += f" -k {keyfile}"
    if write_block0:
        cmd += " --force"  # izinkan menulis blok 0 pada kartu yang mendukung
    return client.run(cmd, timeout=timeout)


def set_magic_uid(client: PM3Client, uid: str,
                  timeout: float = 60.0) -> PM3Result:
    """Set UID pada kartu magic (Gen1a) lewat `hf mf csetuid -u <uid>`.

    `uid` berupa hex tanpa pemisah, mis. '2CD72F90'.
    """
    uid = re.sub(r"[^0-9A-Fa-f]", "", uid)
    return client.run(f"hf mf csetuid -u {uid}", timeout=timeout)


def wipe_gen1a(client: PM3Client, timeout: float = 60.0) -> PM3Result:
    """Kosongkan kartu magic Gen1a ke kondisi awal (`hf mf cwipe`)."""
    return client.run("hf mf cwipe", timeout=timeout)


def verify_clone(client: PM3Client, dumpfile: str,
                 timeout: float = 120.0) -> dict:
    """Bandingkan isi kartu magic Gen1a dengan file dump.

    Membaca kembali kartu via `hf mf cview -f <dump>` tidak ada; kita
    pakai `hf mf cview` lalu serahkan perbandingan ke pengguna, sambil
    mengembalikan output mentah untuk diperiksa.
    """
    res = client.run("hf mf cview", timeout=timeout)
    return {"raw": res.stdout, "ok": res.ok, "dumpfile": dumpfile}
