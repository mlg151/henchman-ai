"""Tests for BUG-011: Zip/Tar Slip in Plugin Archive Extraction.

Verifies that _extract_archive_file rejects archive members with path
traversal components (e.g., ``../../evil.txt``).
"""

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from henchman.extensions.plugin_installer import _extract_archive_file


def _make_zip_with_traversal(tmp_path: Path, entry_name: str) -> Path:
    """Create a zip archive at *tmp_path* containing a single *entry_name*.

    The entry content is harmless; the entry *name* is the attack vector.
    """
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(entry_name, "pwned")
    return archive


def _make_tar_with_traversal(tmp_path: Path, entry_name: str) -> Path:
    """Create a tar archive at *tmp_path* containing a single *entry_name*."""
    archive = tmp_path / "evil.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        info = tarfile.TarInfo(name=entry_name)
        info.size = len(b"pwned")
        info.type = tarfile.REGTYPE
        tf.addfile(info, io.BytesIO(b"pwned"))
    return archive


def _make_plain_zip(tmp_path: Path) -> Path:
    """Create a safe zip archive with no path traversal."""
    archive = tmp_path / "safe.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("safe_file.txt", "hello")
    return archive


def _make_plain_tar(tmp_path: Path) -> Path:
    """Create a safe tar archive with no path traversal."""
    archive = tmp_path / "safe.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        info = tarfile.TarInfo(name="safe_file.txt")
        info.size = len(b"hello")
        info.type = tarfile.REGTYPE
        tf.addfile(info, io.BytesIO(b"hello"))
    return archive


# ---------------------------------------------------------------------------
# Zip slip tests
# ---------------------------------------------------------------------------


class TestZipSlip:
    """_extract_archive_file rejects Zip archives with traversal."""

    def test_rejects_zip_simple_traversal(self, tmp_path: Path) -> None:
        """Zip entry ``../evil.txt`` is rejected."""
        archive = _make_zip_with_traversal(tmp_path, "../evil.txt")
        target = tmp_path / "out"
        target.mkdir()
        with pytest.raises(ValueError, match="outside the target directory"):
            _extract_archive_file(archive, "http://example.com/pkg.zip", target)

    def test_rejects_zip_deep_traversal(self, tmp_path: Path) -> None:
        """Zip entry ``a/../../etc/passwd`` is rejected."""
        archive = _make_zip_with_traversal(tmp_path, "a/../../etc/passwd")
        target = tmp_path / "out"
        target.mkdir()
        with pytest.raises(ValueError, match="outside the target directory"):
            _extract_archive_file(archive, "http://example.com/pkg.zip", target)

    def test_accepts_zip_safe_entry(self, tmp_path: Path) -> None:
        """Safe zip entries extract without error."""
        archive = _make_plain_zip(tmp_path)
        target = tmp_path / "out"
        target.mkdir()
        _extract_archive_file(archive, "http://example.com/pkg.zip", target)
        assert (target / "safe_file.txt").read_text() == "hello"

    def test_rejects_zip_absolute_path(self, tmp_path: Path) -> None:
        """Zip entry ``/etc/passwd`` (absolute) is rejected."""
        archive = _make_zip_with_traversal(tmp_path, "/etc/passwd")
        target = tmp_path / "out"
        target.mkdir()
        with pytest.raises(ValueError, match="outside the target directory"):
            _extract_archive_file(archive, "http://example.com/pkg.zip", target)


# ---------------------------------------------------------------------------
# Tar slip tests
# ---------------------------------------------------------------------------


class TestTarSlip:
    """_extract_archive_file rejects Tar archives with traversal."""

    def test_rejects_tar_simple_traversal(self, tmp_path: Path) -> None:
        """Tar entry ``../evil.txt`` is rejected."""
        archive = _make_tar_with_traversal(tmp_path, "../evil.txt")
        target = tmp_path / "out"
        target.mkdir()
        with pytest.raises(ValueError, match="outside the target directory"):
            _extract_archive_file(
                archive, "http://example.com/pkg.tar.gz", target
            )

    def test_rejects_tar_deep_traversal(self, tmp_path: Path) -> None:
        """Tar entry ``a/../../etc/passwd`` is rejected."""
        archive = _make_tar_with_traversal(tmp_path, "a/../../etc/passwd")
        target = tmp_path / "out"
        target.mkdir()
        with pytest.raises(ValueError, match="outside the target directory"):
            _extract_archive_file(
                archive, "http://example.com/pkg.tar.gz", target
            )

    def test_accepts_tar_safe_entry(self, tmp_path: Path) -> None:
        """Safe tar entries extract without error."""
        archive = _make_plain_tar(tmp_path)
        target = tmp_path / "out"
        target.mkdir()
        _extract_archive_file(
            archive, "http://example.com/pkg.tar.gz", target
        )
        assert (target / "safe_file.txt").read_text() == "hello"

    def test_rejects_tar_absolute_member(self, tmp_path: Path) -> None:
        """Tar entry ``/etc/passwd`` (absolute) is rejected."""
        archive = _make_tar_with_traversal(tmp_path, "/etc/passwd")
        target = tmp_path / "out"
        target.mkdir()
        with pytest.raises(ValueError, match="outside the target directory"):
            _extract_archive_file(
                archive, "http://example.com/pkg.tar.gz", target
            )

    @pytest.mark.parametrize(
        "member_type",
        [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE, tarfile.FIFOTYPE],
        ids=["symlink", "hardlink", "character-device", "block-device", "fifo"],
    )
    def test_rejects_links_and_special_files_before_extracting(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        member_type: bytes,
    ) -> None:
        """Archive-created links cannot overwrite files outside the target."""
        # Model the permissive default on supported Python versions before 3.14.
        if hasattr(tarfile, "fully_trusted_filter"):
            monkeypatch.setattr(
                tarfile.TarFile,
                "extraction_filter",
                staticmethod(tarfile.fully_trusted_filter),
            )
        target = tmp_path / "out"
        target.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("original")
        archive = tmp_path / "special.tar"
        with tarfile.open(archive, "w") as tf:
            safe = tarfile.TarInfo("safe.txt")
            safe.size = 4
            tf.addfile(safe, io.BytesIO(b"safe"))
            special = tarfile.TarInfo("special")
            special.type = member_type
            special.linkname = str(outside)
            tf.addfile(special)
            if member_type in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                payload = tarfile.TarInfo("special")
                payload.size = 7
                tf.addfile(payload, io.BytesIO(b"changed"))

        with pytest.raises(ValueError, match="Unsupported archive member"):
            _extract_archive_file(archive, "https://example.com/pkg.tar", target)

        assert outside.read_text() == "original"
        assert list(target.iterdir()) == []
