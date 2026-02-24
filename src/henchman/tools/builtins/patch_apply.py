"""Patch apply tool implementation."""

import re
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult


class PatchApplyTool(Tool):
    """Apply unified diff patches to files.

    Accepts standard unified diff format with multiple hunks and
    applies them in a single operation. Supports dry-run preview
    and fuzzy context matching.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "patch_apply"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Apply a unified diff patch to one or more files. "
            "Supports multi-hunk patches, dry-run preview, and "
            "fuzzy context matching."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "patch": {
                    "type": "string",
                    "description": "Unified diff patch content",
                },
                "path": {
                    "type": "string",
                    "description": (
                        "Target file path (required for single-file patches "
                        "without file headers)"
                    ),
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview changes without applying",
                    "default": False,
                },
                "fuzz": {
                    "type": "integer",
                    "description": "Lines of fuzz for context matching (default 2)",
                    "default": 2,
                },
            },
            "required": ["patch"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - WRITE because it modifies files."""
        return ToolKind.WRITE

    async def execute(  # type: ignore[override]
        self,
        patch: str = "",
        path: str | None = None,
        dry_run: bool = False,
        fuzz: int = 2,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Apply a unified diff patch.

        Args:
            patch: The unified diff content.
            path: Target file (for headerless patches).
            dry_run: Preview without writing.
            fuzz: Context fuzz lines.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with application status.
        """
        if not patch.strip():
            return ToolResult(
                content="Error: Empty patch",
                success=False,
                error="Empty patch",
            )

        try:
            file_patches = self._parse_patch(patch, default_path=path)
        except ValueError as exc:
            return ToolResult(
                content=f"Error parsing patch: {exc}",
                success=False,
                error=str(exc),
            )

        if not file_patches:
            return ToolResult(
                content="Error: No hunks found in patch",
                success=False,
                error="No hunks",
            )

        results: list[str] = []
        for file_path, hunks in file_patches.items():
            target = Path(file_path)
            if not target.exists():
                results.append(f"SKIP {file_path}: file not found")
                continue

            try:
                original = target.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                results.append(f"SKIP {file_path}: {exc}")
                continue

            try:
                patched = self._apply_hunks(original, hunks, fuzz=fuzz)
            except ValueError as exc:
                results.append(f"FAIL {file_path}: {exc}")
                continue

            if dry_run:
                results.append(f"OK {file_path} (dry run, {len(hunks)} hunks)")
            else:
                target.write_text(patched, encoding="utf-8")
                results.append(f"OK {file_path} ({len(hunks)} hunks applied)")

        return ToolResult(
            content="\n".join(results),
            success=all(r.startswith("OK") for r in results),
        )

    def _parse_patch(
        self,
        patch: str,
        default_path: str | None = None,
    ) -> dict[str, list[dict[str, object]]]:
        """Parse unified diff into file patches.

        Args:
            patch: The unified diff text.
            default_path: Default file path for headerless patches.

        Returns:
            Dict mapping file paths to lists of hunk dicts.

        Raises:
            ValueError: If patch is malformed.
        """
        file_patches: dict[str, list[dict[str, object]]] = {}
        current_file: str | None = default_path
        current_hunk: dict[str, object] | None = None
        hunk_lines: list[str] = []

        lines = patch.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            # File header
            if (
                line.startswith("--- ")
                and i + 1 < len(lines)
                and lines[i + 1].startswith("+++ ")
            ):
                if default_path is None:
                    path_str = lines[i + 1][4:].strip()
                    # Strip a/ or b/ prefix
                    if path_str.startswith("b/"):
                        path_str = path_str[2:]
                    current_file = path_str
                i += 2
                continue

            # Hunk header
            match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if match:
                # Save previous hunk
                if current_hunk is not None and current_file:
                    current_hunk["lines"] = hunk_lines
                    file_patches.setdefault(current_file, []).append(current_hunk)

                old_start = int(match.group(1))
                old_count = int(match.group(2)) if match.group(2) else 1
                new_start = int(match.group(3))
                new_count = int(match.group(4)) if match.group(4) else 1

                current_hunk = {
                    "old_start": old_start,
                    "old_count": old_count,
                    "new_start": new_start,
                    "new_count": new_count,
                }
                hunk_lines = []
                i += 1
                continue

            # Hunk content
            if current_hunk is not None:
                if line.startswith("+") or line.startswith("-") or line.startswith(" "):
                    hunk_lines.append(line)
                elif line == "" and i == len(lines) - 1:
                    pass  # trailing newline
                elif line.startswith("\\"):
                    pass  # "\ No newline at end of file"

            i += 1

        # Save last hunk
        if current_hunk is not None and current_file:
            current_hunk["lines"] = hunk_lines
            file_patches.setdefault(current_file, []).append(current_hunk)

        if not file_patches and default_path is None:
            msg = "No file path found in patch and no default path provided"
            raise ValueError(msg)

        return file_patches

    def _apply_hunks(
        self,
        original: str,
        hunks: list[dict[str, object]],
        fuzz: int = 2,
    ) -> str:
        """Apply hunks to file content.

        Args:
            original: Original file content.
            hunks: List of hunk dicts.
            fuzz: Lines of fuzz for matching.

        Returns:
            Patched file content.

        Raises:
            ValueError: If a hunk fails to apply.
        """
        lines = original.split("\n")
        # Track if original ended with newline
        trailing_newline = original.endswith("\n")
        if trailing_newline and lines and lines[-1] == "":
            lines = lines[:-1]

        offset = 0
        for hunk_idx, hunk in enumerate(hunks):
            old_start = int(str(hunk["old_start"])) - 1 + offset
            hunk_lines: list[str] = list(hunk["lines"])  # type: ignore[arg-type]

            # Extract old and new lines
            old_lines: list[str] = []
            new_lines: list[str] = []
            for hl in hunk_lines:
                if hl.startswith("-"):
                    old_lines.append(hl[1:])
                elif hl.startswith("+"):
                    new_lines.append(hl[1:])
                elif hl.startswith(" "):
                    old_lines.append(hl[1:])
                    new_lines.append(hl[1:])

            # Try exact match first
            matched_start = self._find_match(lines, old_lines, old_start, fuzz)
            if matched_start is None:
                msg = f"Hunk {hunk_idx + 1} failed to apply at line {old_start + 1}"
                raise ValueError(msg)

            # Replace
            lines[matched_start : matched_start + len(old_lines)] = new_lines
            offset += len(new_lines) - len(old_lines)

        result = "\n".join(lines)
        if trailing_newline:
            result += "\n"
        return result

    def _find_match(
        self,
        lines: list[str],
        old_lines: list[str],
        expected_start: int,
        fuzz: int,
    ) -> int | None:
        """Find where old_lines match in the file, with fuzz.

        Args:
            lines: Current file lines.
            old_lines: Lines expected in old version.
            expected_start: Expected start position.
            fuzz: Number of lines to search around expected position.

        Returns:
            Matched start index, or None if no match.
        """
        if not old_lines:
            return max(0, min(expected_start, len(lines)))

        # Try exact position first
        if self._lines_match(lines, old_lines, expected_start):
            return expected_start

        # Try with fuzz
        for delta in range(1, fuzz + 1):
            for candidate in [expected_start - delta, expected_start + delta]:
                if 0 <= candidate <= len(lines) - len(old_lines) and self._lines_match(
                    lines, old_lines, candidate
                ):
                    return candidate

        # Wider search
        for start in range(
            max(0, expected_start - 50), min(len(lines), expected_start + 50)
        ):
            if self._lines_match(lines, old_lines, start):
                return start

        return None

    def _lines_match(
        self,
        lines: list[str],
        old_lines: list[str],
        start: int,
    ) -> bool:
        """Check if old_lines match at the given position.

        Args:
            lines: File lines.
            old_lines: Expected old lines.
            start: Start position.

        Returns:
            True if lines match.
        """
        if start < 0 or start + len(old_lines) > len(lines):
            return False
        return lines[start : start + len(old_lines)] == old_lines
