from pathlib import Path

import pytest
from evals.test_test_docs import _CLAMP_SOURCE, verify_clamp_documentation

GOOD_DOC = "\n".join(
    [
        '"""Clamp.',
        "",
        "    >>> clamp(-2, 0, 5)",
        "    0",
        "    >>> clamp(3, 0, 5)",
        "    3",
        "    >>> clamp(9, 0, 5)",
        "    5",
        "    >>> clamp(0, 4, 1)",
        "    Traceback (most recent call last):",
        "        ...",
        "    ValueError: lower exceeds upper",
        '    """',
    ]
)


@pytest.mark.asyncio
async def test_test_docs_documentation(tmp_path: Path) -> None:
    source = _CLAMP_SOURCE.replace('"""Clamp a value between lower and upper bounds."""', GOOD_DOC)
    bounds = tmp_path / "bounds.py"
    bounds.write_text(source, encoding="utf-8")
    before = bounds.read_bytes()
    await verify_clamp_documentation(tmp_path)
    assert bounds.read_bytes() == before
