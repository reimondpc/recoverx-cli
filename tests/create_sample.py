#!/usr/bin/env python3
"""Generate a sample .img file with embedded files for testing.

Creates a 10 MB disk image containing valid JPEGs and PNGs at known
offsets for end-to-end testing of the carving pipeline.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

SAMPLE_DIR = Path(__file__).parent
OUTPUT = SAMPLE_DIR.parent / "sample.img"
DISK_SIZE = 10 * 1024 * 1024  # 10 MB

try:
    from PIL import Image, ImageDraw

    HAVE_PIL = True
except ImportError:
    HAVE_PIL = False


# ---------------------------------------------------------------------------
# JPEG helpers
# ---------------------------------------------------------------------------


def _make_jpeg_pil(width: int, height: int, r: int, g: int, b: int) -> bytes:
    img = Image.new("RGB", (width, height), (r, g, b))
    draw = ImageDraw.Draw(img)
    draw.ellipse(
        [width // 4, height // 4, width * 3 // 4, height * 3 // 4], fill=(255 - r, 255 - g, 255 - b)
    )
    buf = bytearray()
    img.save(buf, "JPEG", quality=85)
    return bytes(buf)


def _make_jpeg_pure(width: int, height: int, r: int, g: int, b: int) -> bytes:
    qtable = bytes(
        [
            16,
            11,
            10,
            16,
            24,
            40,
            51,
            61,
            12,
            12,
            14,
            19,
            26,
            58,
            60,
            55,
            14,
            13,
            16,
            24,
            40,
            57,
            69,
            56,
            14,
            17,
            22,
            29,
            51,
            87,
            80,
            62,
            18,
            22,
            37,
            56,
            68,
            109,
            103,
            77,
            24,
            35,
            55,
            64,
            81,
            104,
            113,
            92,
            49,
            64,
            78,
            87,
            103,
            121,
            120,
            101,
            72,
            92,
            95,
            98,
            112,
            100,
            103,
            99,
        ]
    )

    def segment(marker: int, payload: bytes) -> bytes:
        return struct.pack(">BH", marker, len(payload) + 2) + payload

    sof0 = segment(
        0xC0,
        struct.pack(">BHH", 8, height, width)
        + struct.pack("BBB", 1, 0x11, 0)
        + struct.pack("BBB", 2, 0x11, 1)
        + struct.pack("BBB", 3, 0x11, 1),
    )
    dqt = segment(0xDB, b"\x00" + qtable + b"\x01" + qtable)
    huff_tables = [
        (0, 0, bytes([0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0]), bytes(range(12))),
        (1, 0, bytes([0, 2, 1, 3, 3, 2, 4, 3, 5, 5, 4, 4, 0, 0, 1, 0x7D]), bytes(range(162))),
        (0, 1, bytes([0, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0]), bytes(range(12))),
        (1, 1, bytes([0, 2, 1, 2, 4, 4, 3, 4, 7, 5, 4, 4, 0, 1, 2, 0x77]), bytes(range(162))),
    ]
    dht = b"".join(
        segment(0xC4, bytes([cls << 4 | id]) + cnts + vals) for cls, id, cnts, vals in huff_tables
    )

    y = max(0, min(255, int(0.299 * r + 0.587 * g + 0.114 * b)))
    cb = max(0, min(255, int(128 - 0.168736 * r - 0.331264 * g + 0.5 * b)))
    cr = max(0, min(255, int(128 + 0.5 * r - 0.418688 * g - 0.081312 * b)))
    blocks = max((width * height) // 64, 1)

    dc_huff_lum = {0: 0b00, 1: 0b010, 2: 0b011, 3: 0b100, 4: 0b101, 5: 0b110, 6: 0b1110, 7: 0b11110}
    dc_huff_chr = {
        0: 0b00,
        1: 0b01,
        2: 0b10,
        3: 0b110,
        4: 0b1110,
        5: 0b11110,
        6: 0b111110,
        7: 0b1111110,
    }

    def block_bits(value: int, is_lum: bool) -> list[int]:
        bits = []
        size = 0 if value == 0 else value.bit_length()
        table = dc_huff_lum if is_lum else dc_huff_chr
        code = table.get(size, 0b11111110)
        code_len = {0: 2, 1: 3, 2: 3, 3: 3, 4: 3, 5: 3, 6: 4, 7: 5}.get(size, 8)
        if not is_lum:
            code_len = {0: 2, 1: 2, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6, 7: 7}.get(size, 8)
        for i in range(code_len - 1, -1, -1):
            bits.append((code >> i) & 1)
        for i in range(size - 1, -1, -1):
            bits.append((value >> i) & 1)
        bits.extend([1, 0, 1, 0] if is_lum else [0, 0])
        return bits

    scan_bits: list[int] = []
    for _ in range(blocks):
        scan_bits.extend(block_bits(y, True))
        scan_bits.extend(block_bits(cb, False))
        scan_bits.extend(block_bits(cr, False))

    scan_data = bytearray()
    acc = 0
    count = 0
    for b in scan_bits:
        acc = (acc << 1) | b
        count += 1
        if count == 8:
            scan_data.append(acc)
            if acc == 0xFF:
                scan_data.append(0x00)
            acc = 0
            count = 0
    if count:
        acc <<= 8 - count
        scan_data.append(acc)

    sos_body = (
        struct.pack(">B", 3)
        + struct.pack("BBB", 1, 0x00, 0x00)
        + struct.pack("BBB", 2, 0x11, 0x01)
        + struct.pack("BBB", 3, 0x11, 0x01)
        + struct.pack(">BBB", 0, 63, 0)
    )
    sos = segment(0xDA, sos_body)

    return (
        b"\xff\xd8\xff"
        + segment(0xE0, b"JFIF\x00" + struct.pack(">BHHBB", 1, 1, 1, 0, 0))
        + dqt
        + sof0
        + dht
        + sos
        + bytes(scan_data)
        + b"\xff\xd9"
    )


def _make_jpeg(width: int, height: int, r: int, g: int, b: int) -> bytes:
    if HAVE_PIL:
        return _make_jpeg_pil(width, height, r, g, b)
    return _make_jpeg_pure(width, height, r, g, b)


# ---------------------------------------------------------------------------
# PNG helpers
# ---------------------------------------------------------------------------


def _make_png_pil(width: int, height: int, r: int, g: int, b: int) -> bytes:
    img = Image.new("RGB", (width, height), (r, g, b))
    draw = ImageDraw.Draw(img)
    draw.rectangle(
        [width // 4, height // 4, width * 3 // 4, height * 3 // 4], fill=(255 - r, 255 - g, 255 - b)
    )
    buf = bytearray()
    img.save(buf, "PNG")
    return bytes(buf)


def _make_png_pure(width: int, height: int, r: int, g: int, b: int) -> bytes:
    """Construct a minimal valid PNG image (no external deps)."""

    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        length = len(data)
        crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
        return struct.pack(">I", length) + chunk_type + data + struct.pack(">I", crc)

    signature = b"\x89PNG\r\n\x1a\n"
    # IHDR: width, height, bit_depth=8, color_type=2 (RGB), compression=0, filter=0, interlace=0
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))

    # IDAT: raw image data (filter byte + RGB pixels per row, zlib-compressed)
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter: None
        for _ in range(width):
            raw.extend([r, g, b])
    compressed = zlib.compress(raw)
    idat = chunk(b"IDAT", compressed)

    iend = chunk(b"IEND", b"")

    return signature + ihdr + idat + iend


def _make_png(width: int, height: int, r: int, g: int, b: int) -> bytes:
    if HAVE_PIL:
        return _make_png_pil(width, height, r, g, b)
    return _make_png_pure(width, height, r, g, b)


# ---------------------------------------------------------------------------
# GIF helpers
# ---------------------------------------------------------------------------


def _make_gif(width: int, height: int, r: int, g: int, b: int) -> bytes:
    header = b"GIF89a"
    lsd = struct.pack("<HHB", width, height, 0xF0)
    gct = bytes([r, g, b, 0, 0, 0]) * 16
    image_descriptor = struct.pack("<BBHHB", 0x2C, 0, 0, width, height, 0x00)
    image_data = (
        b"\x02\x16\x8c\x2d\x99\x87\x2a\x1c\xdc\x33\xa0"
        b"\x02\x75\xec\x95\xfa\xa8\xde\x60\x8c\x04\x91\x4c\x01\x00"
    )
    trailer = b"\x3b"
    return header + lsd + gct + image_descriptor + image_data + trailer


# ---------------------------------------------------------------------------
# BMP helpers
# ---------------------------------------------------------------------------


def _make_bmp(width: int, height: int, r: int, g: int, b: int) -> bytes:
    row_size = ((width * 3 + 3) // 4) * 4
    pixel_data_size = row_size * height
    file_size = 14 + 40 + pixel_data_size
    header = b"BM" + struct.pack("<I", file_size) + b"\x00\x00\x00\x00" + struct.pack("<I", 54)
    dib = struct.pack(
        "<IiiHHIIiiII", 40, width, height, 1, 24, 0, pixel_data_size, 2835, 2835, 0, 0
    )
    pixels = bytearray()
    for y in range(height):
        for x in range(width):
            pixels.extend([b, g, r])
        padding = row_size - width * 3
        pixels.extend(b"\x00" * padding)
    return header + dib + bytes(pixels)


# ---------------------------------------------------------------------------
# PDF helpers
# ---------------------------------------------------------------------------


def _make_pdf(size: int) -> bytes:
    body = (
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    )
    body = body.ljust(max(size - len(b"%%EOF"), len(body)), b"\n")
    return b"%PDF-1.4\n" + body + b"%%EOF"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def create_disk_image() -> None:
    """Generate a 10 MB disk image with embedded JPEGs and PNGs."""
    print(f"Creating {DISK_SIZE // 1024 // 1024} MB disk image...")

    disk = bytearray(DISK_SIZE)
    val = 0xAC
    for i in range(DISK_SIZE):
        disk[i] = val & 0xFF
        val = (val * 1103515245 + 12345) & 0xFFFFFFFF

    jpg1 = _make_jpeg(64, 64, 180, 40, 40)
    jpg2 = _make_jpeg(32, 32, 40, 80, 200)
    png1 = _make_png(48, 48, 20, 180, 120)
    png2 = _make_png(24, 24, 200, 100, 50)
    gif1 = _make_gif(32, 32, 180, 100, 50)
    bmp1 = _make_bmp(64, 64, 40, 180, 200)
    pdf1 = _make_pdf(2048)

    offset_jpg1 = 204800
    offset_jpg2 = 5 * 1024 * 1024 + 128
    offset_png1 = 3 * 1024 * 1024
    offset_png2 = 7 * 1024 * 1024 + 512
    offset_gif1 = 2 * 1024 * 1024
    offset_bmp1 = 6 * 1024 * 1024
    offset_pdf1 = 8 * 1024 * 1024

    assert offset_jpg1 + len(jpg1) <= DISK_SIZE
    assert offset_jpg2 + len(jpg2) <= DISK_SIZE
    assert offset_png1 + len(png1) <= DISK_SIZE
    assert offset_png2 + len(png2) <= DISK_SIZE
    assert offset_gif1 + len(gif1) <= DISK_SIZE
    assert offset_bmp1 + len(bmp1) <= DISK_SIZE
    assert offset_pdf1 + len(pdf1) <= DISK_SIZE

    disk[offset_jpg1 : offset_jpg1 + len(jpg1)] = jpg1
    disk[offset_jpg2 : offset_jpg2 + len(jpg2)] = jpg2
    disk[offset_png1 : offset_png1 + len(png1)] = png1
    disk[offset_png2 : offset_png2 + len(png2)] = png2
    disk[offset_gif1 : offset_gif1 + len(gif1)] = gif1
    disk[offset_bmp1 : offset_bmp1 + len(bmp1)] = bmp1
    disk[offset_pdf1 : offset_pdf1 + len(pdf1)] = pdf1

    OUTPUT.write_bytes(bytes(disk))
    print(f"  Saved to    {OUTPUT}")
    print(f"  JPEG #1 at  {offset_jpg1:,} ({len(jpg1)} B)")
    print(f"  JPEG #2 at  {offset_jpg2:,} ({len(jpg2)} B)")
    print(f"  PNG  #1 at  {offset_png1:,} ({len(png1)} B)")
    print(f"  PNG  #2 at  {offset_png2:,} ({len(png2)} B)")
    print(f"  GIF  #1 at  {offset_gif1:,} ({len(gif1)} B)")
    print(f"  BMP  #1 at  {offset_bmp1:,} ({len(bmp1)} B)")
    print(f"  PDF  #1 at  {offset_pdf1:,} ({len(pdf1)} B)")
    print("  Done.")


if __name__ == "__main__":
    create_disk_image()
