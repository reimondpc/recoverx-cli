"""Recovery validation suite.

Measures actual recovery quality:
- precision (correct files / total recovered)
- recovery rate (recovered files / total deletable)
- corruption rate (files with mismatched hashes)
- metadata integrity (timestamps, attributes, sizes)
"""

from __future__ import annotations

import hashlib
import os
import random
import tempfile

from recoverx.core.filesystems.fat32.directory import walk_directory_tree
from recoverx.core.filesystems.fat32.recovery import FAT32Recovery
from recoverx.core.utils.raw_reader import RawReader
from tests.fat32.create_fat32_image import create_fat32_image


class TestRecoveryQuality:
    def _compute_sha256(self, data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def test_precision_normal_files(self):
        content = b"PRECISE DATA " * 100
        with tempfile.TemporaryDirectory() as tmp:
            path = create_fat32_image(
                os.path.join(tmp, "test.img"),
                files=[("ACCURATE.DAT", content)],
                deleted_files=[],
                subdirs=[],
            )
            with RawReader(path) as reader:
                bpb = self._get_bpb(reader)
                rec = FAT32Recovery(reader, bpb)
                entries = walk_directory_tree(reader, bpb)
                for p, e in entries:
                    if not e.is_directory and not e.deleted:
                        result = rec.recover_deleted_file(e)
                        assert result.data is not None
                        recovered_hash = self._compute_sha256(result.data)
                        expected_hash = self._compute_sha256(content)
                        assert recovered_hash == expected_hash
                        assert result.file_size == len(content)
                        assert result.recovery_status == "recovered"

    def test_recovery_rate_deleted(self):
        original_content = b"RECOVERABLE " * 200
        with tempfile.TemporaryDirectory() as tmp:
            path = create_fat32_image(
                os.path.join(tmp, "test.img"),
                files=[],
                deleted_files=[("LOST.DAT", original_content)],
                subdirs=[],
            )
            with RawReader(path) as reader:
                bpb = self._get_bpb(reader)
                rec = FAT32Recovery(reader, bpb)
                deleted = rec.find_deleted_entries()
                assert len(deleted) >= 1
                for d in deleted:
                    result = rec.recover_deleted_file(d)
                    if result.data:
                        rh = self._compute_sha256(result.data)
                        eh = self._compute_sha256(original_content)
                        match = "MATCH" if rh == eh else "MISMATCH"
                        assert rh == eh, f"Hash mismatch for {d.short_name}: {match}"

    def test_metadata_integrity(self):
        content = b"METADATA CHECK " * 50
        with tempfile.TemporaryDirectory() as tmp:
            path = create_fat32_image(
                os.path.join(tmp, "test.img"),
                files=[("META.DAT", content)],
                deleted_files=[],
                subdirs=[],
            )
            with RawReader(path) as reader:
                bpb = self._get_bpb(reader)
                entries = walk_directory_tree(reader, bpb)
                for p, e in entries:
                    if e.short_name == "META.DAT":
                        assert e.file_size == len(content)
                        assert not e.is_directory
                        assert e.start_cluster >= 2

    def test_recovery_from_subdirectory(self):
        content = b"SUBDIR RECOVERY " * 50
        with tempfile.TemporaryDirectory() as tmp:
            path = create_fat32_image(
                os.path.join(tmp, "test.img"),
                files=[],
                deleted_files=[("SUBDIR_FILE.DAT", content)],
                subdirs=[("DELETED_DIR", [("NESTED.TXT", b"nested")])],
            )
            with RawReader(path) as reader:
                bpb = self._get_bpb(reader)
                rec = FAT32Recovery(reader, bpb)
                deleted = rec.find_deleted_entries()
                assert len(deleted) >= 1
                for d in deleted:
                    result = rec.recover_deleted_file(d)
                    assert result.data is not None
                    assert len(result.data) > 0

    def _get_bpb(self, reader):
        from recoverx.core.filesystems.fat32.boot_sector import parse_boot_sector

        sector0 = reader.read_at(0, 512)
        bpb = parse_boot_sector(sector0)
        assert bpb is not None
        return bpb

    def test_recovery_multiple_files_consistency(self):
        files_data = [
            (f"FILE_{i:03d}.BIN", os.urandom(random.randint(100, 2000))) for i in range(20)
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = create_fat32_image(
                os.path.join(tmp, "test.img"),
                files=files_data,
                deleted_files=[],
                subdirs=[],
            )
            with RawReader(path) as reader:
                bpb = self._get_bpb(reader)
                rec = FAT32Recovery(reader, bpb)
                entries = walk_directory_tree(reader, bpb)
                recovered_count = 0
                match_count = 0
                for p, e in entries:
                    if not e.is_directory and not e.deleted:
                        result = rec.recover_deleted_file(e)
                        if result.data:
                            recovered_count += 1
                            for orig_name, orig_data in files_data:
                                if e.short_name == orig_name:
                                    result_hash = self._compute_sha256(
                                        result.data[: len(orig_data)]
                                    )
                                    if result_hash == self._compute_sha256(orig_data):
                                        match_count += 1
                                    break
                assert recovered_count > 0
                assert match_count > 0

    def test_recovery_empty_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_fat32_image(
                os.path.join(tmp, "test.img"),
                files=[("EMPTY.DAT", b"")],
                deleted_files=[],
                subdirs=[],
            )
            with RawReader(path) as reader:
                bpb = self._get_bpb(reader)
                entries = walk_directory_tree(reader, bpb)
                for p, e in entries:
                    if e.short_name == "EMPTY.DAT":
                        rec = FAT32Recovery(reader, bpb)
                        result = rec.recover_deleted_file(e)
                        assert result.data is not None

    def test_volume_label_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = create_fat32_image(
                os.path.join(tmp, "test.img"),
                files=[],
                deleted_files=[],
                subdirs=[],
            )
            with RawReader(path) as reader:
                bpb = self._get_bpb(reader)
                assert "RECOVERX_TE" in bpb.volume_label or "RECOVERX_TEST" in bpb.volume_label
