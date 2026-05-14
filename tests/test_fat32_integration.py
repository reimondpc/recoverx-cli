from __future__ import annotations

import os
import tempfile

import pytest

from recoverx.core.filesystems.fat32.boot_sector import (
    parse_boot_sector,
    validate_boot_sector,
)
from recoverx.core.filesystems.fat32.directory import read_directory, walk_directory_tree
from recoverx.core.filesystems.fat32.recovery import FAT32Recovery
from recoverx.core.utils.raw_reader import RawReader
from tests.fat32.create_fat32_image import create_fat32_image, create_test_image


class TestFAT32Integration:
    def test_full_pipeline_parses_boot_sector(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_test_image(tmp)
            with RawReader(path) as reader:
                sector0 = reader.read_at(0, 512)
                bpb = parse_boot_sector(sector0)
                assert bpb is not None
                assert bpb.bytes_per_sector == 512
                assert bpb.signature_valid

    def test_reads_root_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_test_image(tmp)
            with RawReader(path) as reader:
                sector0 = reader.read_at(0, 512)
                bpb = parse_boot_sector(sector0)
                assert bpb
                entries = read_directory(reader, bpb, bpb.root_cluster)
                assert len(entries) >= 4

    def test_walks_directory_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_test_image(tmp)
            with RawReader(path) as reader:
                sector0 = reader.read_at(0, 512)
                bpb = parse_boot_sector(sector0)
                assert bpb
                entries = walk_directory_tree(reader, bpb)
                print(f"Walk found {len(entries)} entries")
                for p, e in entries:
                    print(f"  {p}")
                assert len(entries) >= 5

    def test_finds_deleted_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_test_image(tmp)
            with RawReader(path) as reader:
                sector0 = reader.read_at(0, 512)
                bpb = parse_boot_sector(sector0)
                assert bpb
                rec = FAT32Recovery(reader, bpb)
                deleted = rec.find_deleted_entries()
                assert len(deleted) >= 1

    def test_recovers_deleted_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_test_image(tmp)
            with RawReader(path) as reader:
                sector0 = reader.read_at(0, 512)
                bpb = parse_boot_sector(sector0)
                assert bpb
                rec = FAT32Recovery(reader, bpb)
                deleted = rec.find_deleted_entries()
                for d in deleted:
                    result = rec.recover_deleted_file(d)
                    assert result.data is not None
                    assert len(result.sha256) == 64
                    assert result.recovery_status in ("recovered", "truncated")

    def test_recovered_content_matches(self):
        content = b"UNIQUE CONTENT FOR TESTING " * 50
        with tempfile.TemporaryDirectory() as tmp:
            path = create_fat32_image(
                os.path.join(tmp, "test.img"),
                files=[("VERIFY.DAT", content)],
                deleted_files=[],
                subdirs=[],
            )
            with RawReader(path) as reader:
                sector0 = reader.read_at(0, 512)
                bpb = parse_boot_sector(sector0)
                assert bpb
                rec = FAT32Recovery(reader, bpb)

                entries = read_directory(reader, bpb, bpb.root_cluster)
                for e in entries:
                    if e.short_name == "VERIFY.DAT":
                        result = rec.recover_deleted_file(e)
                        assert result.data == content[: len(result.data)]
                        return
            pytest.fail("VERIFY.DAT not found")

    def test_subdirectory_navigation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_test_image(tmp)
            with RawReader(path) as reader:
                sector0 = reader.read_at(0, 512)
                bpb = parse_boot_sector(sector0)
                assert bpb
                entries = walk_directory_tree(reader, bpb)
                subdir_entries = [p for p, e in entries if "SUBDIR" in p]
                assert len(subdir_entries) > 0

    def test_validate_real_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_test_image(tmp)
            with RawReader(path) as reader:
                sector0 = reader.read_at(0, 512)
                bpb = parse_boot_sector(sector0)
                assert bpb
                issues = validate_boot_sector(bpb)
                assert isinstance(issues, list)

    def test_recovery_to_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_test_image(tmp)
            with RawReader(path) as reader:
                sector0 = reader.read_at(0, 512)
                bpb = parse_boot_sector(sector0)
                assert bpb
                rec = FAT32Recovery(reader, bpb)
                deleted = rec.find_deleted_entries()
                for d in deleted:
                    result = rec.recover_deleted_file(d)
                    if result.data:
                        saved = rec.save_recovered(result, output_dir=tmp)
                        assert os.path.exists(saved)
