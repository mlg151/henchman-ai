"""Numbered reads preserve source coordinates and bounded output."""

from pathlib import Path

import pytest

from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_read import ReadFileTool


async def test_default_read_remains_exact_text(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    content = "first\n\nlast"
    path.write_text(content)
    result = await ReadFileTool().execute(path=str(path))
    assert result.success
    assert result.content == content


async def test_numbered_range_uses_absolute_lines(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("first\n\nthird\nlast")
    result = await ReadFileTool().execute(
        path=str(path), start_line=2, end_line=3, line_numbers=True
    )
    assert result.success
    assert result.content == "2: \n3: third\n"


async def test_numbered_read_preserves_unterminated_final_line(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("first\nlast")
    result = await ReadFileTool().execute(path=str(path), line_numbers=True)
    assert result.content == "1: first\n2: last"


async def test_number_prefixes_count_toward_character_budget(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("abc\ndef\n")
    result = await ReadFileTool().execute(path=str(path), line_numbers=True, max_chars=8)
    assert result.content == "1: abc\n2\n... (truncated after 8 chars)"


async def test_numbered_read_coordinates_support_edit_and_reread(tmp_path: Path) -> None:
    path = tmp_path / "sample.py"
    path.write_text("before\ntmp = []\nbetween\ntmp = []\nafter\n")
    reader = ReadFileTool()
    result = await reader.execute(path=str(path), start_line=3, line_numbers=True)
    assert result.content == "3: between\n4: tmp = []\n5: after\n"
    edited = await EditFileTool().execute(
        path=str(path), start_line=4, end_line=4, new_str="result = []\nresult.append(1)"
    )
    assert edited.success
    assert path.read_text() == "before\ntmp = []\nbetween\nresult = []\nresult.append(1)\nafter\n"
    reread = await reader.execute(path=str(path), start_line=5, line_numbers=True)
    assert reread.content == "5: result.append(1)\n6: after\n"


@pytest.mark.parametrize("separator", ["\f", "\v", "\u0085", "\u2028", "\u2029"])
async def test_edit_uses_same_physical_lines_as_numbered_read(
    tmp_path: Path, separator: str
) -> None:
    path = tmp_path / "sample.txt"
    path.write_text(f"before{separator}hidden\ntarget\nafter\n")
    result = await ReadFileTool().execute(path=str(path), line_numbers=True)
    assert result.content == f"1: before{separator}hidden\n2: target\n3: after\n"
    edited = await EditFileTool().execute(
        path=str(path), start_line=2, end_line=2, new_str="replacement"
    )
    assert edited.success
    assert path.read_text() == f"before{separator}hidden\nreplacement\nafter\n"
