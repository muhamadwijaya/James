"""Penampil isi dump MIFARE Classic: hex + ASCII berdampingan.

Membaca file dump hasil PM3 (.bin / .eml / .json) lalu menampilkan tiap
blok dalam hex dan ASCII, dikelompokkan per sektor, dengan baris trailer
(KeyA | AccessBits/GPB | KeyB) ditandai. Tidak butuh perangkat.
"""

from __future__ import annotations

import json
import os
import re

BLOCK_SIZE = 16


def _printable(b: int) -> str:
    return chr(b) if 0x20 <= b <= 0x7E else "."


def load_dump(path: str) -> bytes:
    """Muat dump dari .bin (mentah), .eml (teks hex per baris), atau .json.

    Mengembalikan byte mentah (kelipatan 16).
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".bin" or ext == "":
        with open(path, "rb") as f:
            return f.read()
    if ext == ".eml":
        data = bytearray()
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                hexstr = re.sub(r"[^0-9A-Fa-f]", "", line)
                if hexstr:
                    data += bytes.fromhex(hexstr)
        return bytes(data)
    if ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        blocks = obj.get("blocks", {})
        # urutkan berdasarkan nomor blok numerik
        data = bytearray()
        for k in sorted(blocks, key=lambda x: int(x)):
            data += bytes.fromhex(blocks[k])
        return bytes(data)
    raise ValueError(f"Format tidak dikenal: {ext} (pakai .bin/.eml/.json)")


def _num_blocks(total_bytes: int) -> int:
    return total_bytes // BLOCK_SIZE


def sector_layout(total_bytes: int) -> list[tuple[int, list[int]]]:
    """Kembalikan [(sector_index, [block_nums...]), ...].

    Mendukung 1K (16 sektor × 4 blok) dan 4K (32 sektor × 4 blok lalu
    8 sektor × 16 blok). Ukuran lain dibagi per 4 blok.
    """
    n = _num_blocks(total_bytes)
    layout: list[tuple[int, list[int]]] = []
    sector = 0
    blk = 0
    if n > 128:  # 4K: 32 sektor kecil + 8 sektor besar
        while blk < n:
            size = 4 if sector < 32 else 16
            blocks = list(range(blk, min(blk + size, n)))
            layout.append((sector, blocks))
            blk += size
            sector += 1
    else:
        while blk < n:
            blocks = list(range(blk, min(blk + 4, n)))
            layout.append((sector, blocks))
            blk += 4
            sector += 1
    return layout


def _is_trailer(blocks: list[int], blocknum: int) -> bool:
    return blocknum == blocks[-1]


def block_hex(b: bytes, group: int = 1) -> str:
    if group <= 1:
        return " ".join(f"{x:02X}" for x in b)
    out = []
    for i in range(0, len(b), group):
        out.append("".join(f"{x:02X}" for x in b[i:i + group]))
    return " ".join(out)


def block_ascii(b: bytes) -> str:
    return "".join(_printable(x) for x in b)


def _trailer_fields(b: bytes) -> str:
    key_a = b[0:6].hex().upper()
    acc = b[6:10].hex().upper()   # 3 byte access + 1 byte GPB
    key_b = b[10:16].hex().upper()
    return f"KeyA={key_a}  AC/GPB={acc}  KeyB={key_b}"


def parse_sectors_arg(arg: str | None, max_sector: int) -> set[int] | None:
    """'1-4', '1,3,5', '1-4,7' -> set sektor. None/'' -> semua."""
    if not arg:
        return None
    result: set[int] = set()
    for part in arg.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            result.update(range(int(a), int(b) + 1))
        else:
            result.add(int(part))
    return {s for s in result if 0 <= s <= max_sector}


def format_dump(data: bytes, sectors: set[int] | None = None,
                mode: str = "both") -> str:
    """Render dump jadi teks. mode: 'hex' | 'ascii' | 'both'."""
    if not data:
        return "(dump kosong)"
    layout = sector_layout(len(data))
    lines: list[str] = []
    for sector, blocks in layout:
        if sectors is not None and sector not in sectors:
            continue
        lines.append(f"── Sector {sector} " + "─" * 40)
        for blocknum in blocks:
            off = blocknum * BLOCK_SIZE
            b = data[off:off + BLOCK_SIZE]
            if len(b) < BLOCK_SIZE:
                b = b + bytes(BLOCK_SIZE - len(b))
            trailer = _is_trailer(blocks, blocknum)
            prefix = f" blk {blocknum:3d}"
            if trailer:
                prefix += " [trailer]"
            if mode == "hex":
                body = block_hex(b)
            elif mode == "ascii":
                body = block_ascii(b)
            else:  # both
                body = f"{block_hex(b)}  |{block_ascii(b)}|"
            lines.append(f"{prefix}  {body}")
            if trailer and mode != "ascii":
                lines.append(f"            {_trailer_fields(b)}")
    return "\n".join(lines)


def view_file(path: str, sectors_arg: str | None = None,
              mode: str = "both") -> str:
    data = load_dump(path)
    max_sector = len(sector_layout(len(data))) - 1
    sectors = parse_sectors_arg(sectors_arg, max_sector)
    header = (f"Dump: {os.path.basename(path)}  "
              f"({len(data)} byte, {_num_blocks(len(data))} blok, "
              f"{max_sector + 1} sektor)\n")
    return header + format_dump(data, sectors=sectors, mode=mode)
