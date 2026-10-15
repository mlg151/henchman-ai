"""Contracts for recovering from ambiguous or malformed edit targets."""

from pathlib import Path
from typing import Any

import pytest

from henchman.tools.builtins.file_edit import EditFileTool


@pytest.mark.parametrize(
    "target",
    [
        {"start_line": 1},
        {"end_line": 2},
        {"old_str": "first", "start_line": 1},
        {"old_str": "first", "end_line": 2},
        {"old_str": "first", "start_line": 1, "end_line": 2},
    ],
)
async def test_incomplete_or_mixed_targets_fail_without_writing(
    tmp_path: Path,
    target: dict[str, Any],
) -> None:
    path = tmp_path / "sample.txt"
    original = b"first\nsecond\n"
    path.write_bytes(original)
    result = await EditFileTool().execute(path=str(path), new_str="changed", **target)
    assert not result.success
    assert path.read_bytes() == original
    assert "old_str" in result.content
    assert "start_line" in result.content
    assert "end_line" in result.content
    assert "either" in result.content.lower()


async def test_ambiguous_match_guides_unique_context_retry(tmp_path: Path) -> None:
    path = tmp_path / "processor.py"
    original = "def first():\n    tmp = []\n\ndef second():\n    tmp = []\n"
    path.write_text(original)
    tool = EditFileTool()
    result = await tool.execute(path=str(path), old_str="tmp = []", new_str="result = []")
    assert not result.success
    assert path.read_text() == original
    message = result.content.lower()
    assert "read_file" in message
    assert "surrounding context" in message
    assert "unique" in message
    assert "do not guess" in message

    # A retry uses a complete, unique surrounding block from the current file.
    result = await tool.execute(
        path=str(path),
        old_str="def second():\n    tmp = []",
        new_str="def second():\n    result = []",
    )
    assert result.success
    assert path.read_text() == original.replace(
        "def second():\n    tmp = []",
        "def second():\n    result = []",
    )


def test_tool_guidance_explains_current_inclusive_range_replacement() -> None:
    tool = EditFileTool()
    description = tool.description.lower()
    assert "entire" in description
    assert "current" in description
    assert "line numbers" in description
    properties = tool.parameters["properties"]
    assert isinstance(properties, dict)
    assert "entire" in properties["new_str"]["description"].lower()
    assert "current" in properties["start_line"]["description"].lower()
    assert "inclusive" in properties["end_line"]["description"].lower()


async def test_complete_range_retains_eof_clamping(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("first\nsecond\nthird\n")
    result = await EditFileTool().execute(
        path=str(path),
        start_line=2,
        end_line=99,
        new_str="replacement\n",
    )
    assert result.success
    assert path.read_text() == "first\nreplacement\n"
