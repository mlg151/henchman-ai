"""Generated evaluation sources must be valid UTF-8 under locale defaults."""

import os
from pathlib import Path

import pytest
from evals.helpers import EvalTestRig, MockProvider


def test_eval_fixture_encoding(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise real fixture writing with a CP1252 default at the target path."""
    rig = EvalTestRig(provider=MockProvider([]))
    try:
        rig.setup("encoding_test")
        target = rig.test_dir / "test_unicode.py"
        original_write_text = Path.write_text
        observed_encodings: list[str | None] = []

        def mocked_write_text(
            path: Path, content: str, encoding: str | None = None,
            errors: str | None = None, newline: str | None = None,
        ) -> int:
            if path == target:
                observed_encodings.append(encoding)
                encoding = encoding or "cp1252"
            return original_write_text(
                path, content, encoding=encoding, errors=errors, newline=newline,
            )

        monkeypatch.setattr(Path, "write_text", mocked_write_text)
        content = 'value = "Straße 東京"\n'
        path = rig.create_file("test_unicode.py", content)
        assert path == target
        actual = path.read_bytes()
        assert actual == content.replace("\n", os.linesep).encode("utf-8")
        namespace: dict[str, object] = {}
        exec(compile(actual, str(path), "exec"), namespace)
        assert namespace["value"] == "Straße 東京"
        assert observed_encodings == ["utf-8"]
    finally:
        rig.cleanup()
