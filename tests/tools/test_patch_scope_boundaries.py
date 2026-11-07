"""Unified diff headers cannot move a pending hunk into another file's scope."""

from henchman.tools.builtins.patch_apply import PatchParser


def test_next_file_header_flushes_hunks_under_the_original_file() -> None:
    patch = (
        "--- a/left/data.txt\n+++ b/left/data.txt\n@@ -1 +1 @@\n-left\n+LEFT\n"
        "--- a/right/data.txt\n+++ b/right/data.txt\n@@ -1 +1 @@\n-right\n+RIGHT\n"
    )
    parsed = PatchParser(patch).parse()
    assert list(parsed) == ["left/data.txt", "right/data.txt"]
    assert parsed["left/data.txt"][0]["lines"] == ["-left", "+LEFT"]
    assert parsed["right/data.txt"][0]["lines"] == ["-right", "+RIGHT"]
