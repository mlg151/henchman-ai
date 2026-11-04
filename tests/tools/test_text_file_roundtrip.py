import anyio
import pytest

from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_read import ReadFileTool


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
async def test_text_file_roundtrip_newlines(ending, tmp_path, monkeypatch):
    fixture_path = str(tmp_path / "fixture.txt")

    header = "café ❄️\u2028"
    target = "target"
    tail = "tail"

    text = f"{header}{ending}{target}{ending}{tail}{ending}"

    canonical_lf_text = f"{header}\n{target}\n{tail}\n"

    original_open_file = anyio.open_file

    async def wrapper(path, *args, **kwargs):
        if path == tmp_path / "fixture.txt" and kwargs.get("encoding") is None:
            kwargs["encoding"] = "cp1252"
        return await original_open_file(path, *args, **kwargs)

    monkeypatch.setattr(anyio, "open_file", wrapper)

    p = tmp_path / "fixture.txt"
    p.write_bytes(text.encode("utf-8"))

    read_result = await ReadFileTool().execute(path=fixture_path)
    assert read_result.success is True
    assert read_result.content == canonical_lf_text

    edit_result = await EditFileTool().execute(
        path=fixture_path, old_str="target\n", new_str="replacement\n"
    )
    assert edit_result.success is True
    assert p.read_bytes() == canonical_lf_text.replace("target\n", "replacement\n").encode("utf-8")


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
async def test_text_file_roundtrip_with_line_numbers(ending, tmp_path):
    fixture_path = str(tmp_path / "fixture_line_numbers.txt")
    header = "a café/snowman header with \u2028"
    target = "target"
    tail = "tail"

    text = f"{header}{ending}{target}{ending}{tail}{ending}"
    canonical_lf_with_prefixes = f"1: {header}\n2: {target}\n3: {tail}\n"
    expected_full_content = f"{header}\nreplacement\n{tail}\n"

    (tmp_path / "fixture_line_numbers.txt").write_bytes(text.encode("utf-8"))

    reader = ReadFileTool()
    result = await reader.execute(path=fixture_path, line_numbers=True)
    assert result.success is True
    assert result.content == canonical_lf_with_prefixes

    editor = EditFileTool()
    edit = await editor.execute(
        path=fixture_path, start_line=2, end_line=2, new_str="replacement\n"
    )
    assert edit.success is True
    assert (tmp_path / "fixture_line_numbers.txt").read_bytes() == expected_full_content.encode(
        "utf-8"
    )
