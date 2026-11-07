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
@pytest.mark.parametrize(
    "variant", ["complete", "missing-required", "extra-failure", "changed-implementation"]
)
async def test_test_docs_documentation(tmp_path: Path, variant: str) -> None:
    doc = GOOD_DOC
    if variant == "missing-required":
        doc = doc.replace("    >>> clamp(9, 0, 5)\n    5\n", "    >>> 1 + 1\n    2\n")
    elif variant == "extra-failure":
        doc = doc.replace('    """', '    >>> 1 + 1\n    3\n    """')

    source = _CLAMP_SOURCE.replace('"""Clamp a value between lower and upper bounds."""', doc)
    if variant == "changed-implementation":
        source = source.replace(
            "return max(lower, min(value, upper))",
            "return max(lower, min(value, upper)) + (value == 4242)",
        )

    bounds = tmp_path / "bounds.py"
    bounds.write_text(source, encoding="utf-8")
    before = bounds.read_bytes()

    if variant == "complete":
        await verify_clamp_documentation(tmp_path)
    else:
        with pytest.raises(AssertionError):
            await verify_clamp_documentation(tmp_path)

    assert bounds.read_bytes() == before
