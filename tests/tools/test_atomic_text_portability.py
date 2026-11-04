import pytest

from henchman.tools.security import atomic_read, atomic_write


def test_atomic_read_preserves_crlf(tmp_path):
    content = "café\r\nsecond\r\n"
    path = tmp_path / "test_crlf.txt"
    path.write_bytes(content.encode("utf-8"))

    # Text reads preserve the original physical line endings.
    assert atomic_read(str(path)) == content


@pytest.mark.parametrize(
    "content",
    [
        "line1\nline2\n",
        "line1\r\nline2\r\n",
        "café\r\nsecond\r\n",
    ],
)
def test_atomic_write_preserves_bytes(tmp_path, content):
    path = tmp_path / "test_atomic_write.txt"

    atomic_write(str(path), content, encoding="utf-8")

    assert path.read_bytes() == content.encode("utf-8")

    # Check that no .tmp file remains
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0
