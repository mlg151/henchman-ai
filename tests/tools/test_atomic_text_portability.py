import pytest

from henchman.tools.security import atomic_read, atomic_write


@pytest.mark.parametrize(
    "content",
    [
        "café\nsecond\n",
        "café\r\nsecond\r\n",
        "café\rsecond\r",
    ],
)
def test_atomic_read_normalizes_to_lf(tmp_path, content):
    path = tmp_path / "test_atomic_read.txt"
    path.write_bytes(content.encode("utf-8"))

    assert atomic_read(str(path)) == "café\nsecond\n"


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
