"""Create stress test datasets for FAT32 recovery validation.

Generates images with various corruption patterns, fragmentation,
deep directories, and edge cases to validate parser robustness.
"""

from __future__ import annotations

import os
import random
import struct
import tempfile

from recoverx.core.filesystems.fat32.structures import FAT32BootSector

random.seed(42)


def create_corrupted_boot_sector(path: str, corruption_offset: int = 0) -> str:
    """Create image with corrupted boot sector fields."""
    from tests.fat32.create_fat32_image import create_fat32_image

    img_path = create_fat32_image(path)
    with open(img_path, "r+b") as f:
        data = bytearray(f.read(512))
        if corruption_offset < len(data):
            data[corruption_offset] = random.randint(0, 255)
        f.seek(0)
        f.write(bytes(data))
    return img_path


def create_fragmented_image(path: str, num_files: int = 50) -> str:
    """Create image with highly fragmented files."""
    from tests.fat32.create_fat32_image import create_fat32_image

    files = [(f"FRAG_{i:03d}.DAT", os.urandom(random.randint(100, 5000))) for i in range(num_files)]
    return create_fat32_image(
        path, files=files, deleted_files=[], subdirs=["DEEP/DIR/SUBDIR"]
    )


def create_deep_directory_image(path: str, depth: int = 20) -> str:
    """Create image with deeply nested directories."""
    from tests.fat32.create_fat32_image import create_fat32_image

    subdirs = ["/".join([f"LVL_{d}" for d in range(depth)])]
    return create_fat32_image(
        path, files=[("DEEP.txt", b"deep file")], deleted_files=[], subdirs=subdirs
    )


def create_partially_overwritten_image(path: str) -> str:
    """Create image where deleted file data is partially overwritten."""
    from tests.fat32.create_fat32_image import create_fat32_image

    img_path = create_fat32_image(
        path, files=[("NEW.DAT", b"X" * 512 * 10)], deleted_files=[("OLD.DAT", b"Y" * 512 * 10)]
    )
    with open(img_path, "r+b") as f:
        f.seek(512 * 100)
        f.write(b"\x00" * 512 * 3)
    return img_path


def create_fat_loop_image(path: str) -> str:
    """Create image with a FAT entry that loops to itself."""
    from tests.fat32.create_fat32_image import create_fat32_image

    img_path = create_fat32_image(
        path, files=[("LOOP.DAT", b"A" * 512)], deleted_files=[]
    )
    with open(img_path, "r+b") as f:
        bp = FAT32BootSector(
            bytes_per_sector=512, sectors_per_cluster=1, reserved_sectors=32,
            fat_count=2, fat_size_sectors=8, total_sectors=51200,
        )
        fat_off = bp.fat_start + 3 * 4
        f.seek(fat_off)
        f.write(struct.pack("<I", 3))
    return img_path


def create_orphan_cluster_image(path: str) -> str:
    """Create image with data in clusters not referenced by any directory entry."""
    from tests.fat32.create_fat32_image import create_fat32_image

    img_path = create_fat32_image(
        path, files=[("KNOWN.DAT", b"visible")], deleted_files=[], subdirs=[]
    )
    with open(img_path, "r+b") as f:
        f.seek(512 * 200)
        f.write(b"ORPHAN CLUSTER DATA " * 100)
        bp = FAT32BootSector(
            bytes_per_sector=512, sectors_per_cluster=1, reserved_sectors=32,
            fat_count=2, fat_size_sectors=8, total_sectors=51200,
        )
        fat_off = bp.fat_start + 50 * 4
        f.seek(fat_off)
        struct.pack_into("<I", bytearray(4), 0, 51)
        f.write(struct.pack("<I", 0x0FFFFFFF))
        f.seek(fat_off + 4)
        f.write(struct.pack("<I", 0x0FFFFFFF))
    return img_path


def create_large_image(path: str, size_mb: int = 100) -> str:
    """Create a large FAT32 image for stress testing (>1GB)."""
    from tests.fat32.create_fat32_image import create_fat32_image

    large_file_size = min(size_mb * 1024 * 1024 // 2, 500 * 1024 * 1024)
    file_data = os.urandom(min(large_file_size, 1024 * 1024))
    file_data = (file_data * (large_file_size // len(file_data) + 1))[:large_file_size]
    return create_fat32_image(
        path,
        files=[("LARGE.BIN", file_data)],
        deleted_files=[("GONE.DAT", b"deleted" * 1000)],
        subdirs=["DATA", "DATA/ARCHIVE", "DATA/TEMP"],
    )


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as tmp:
        print("Creating stress test images...")
        for name, fn, desc in [
            ("corrupted_boot.img", create_corrupted_boot_sector, "Corrupted boot sector"),
            ("fragmented.img", create_fragmented_image, "Fragmented files (50)"),
            ("deep_dirs.img", create_deep_directory_image, "Deep directory nesting"),
            ("overwritten.img", create_partially_overwritten_image, "Partially overwritten"),
            ("fat_loop.img", create_fat_loop_image, "FAT self-loop"),
            ("orphan.img", create_orphan_cluster_image, "Orphan clusters"),
            ("large.img", create_large_image, "Large image (100MB)"),
        ]:
            path = os.path.join(tmp, name)
            result = fn(path)
            print(f"  {desc}: {result} ({os.path.getsize(result)} bytes)")
        print("Done.")
