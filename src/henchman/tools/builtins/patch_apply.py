"""Patch apply tool implementation."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from henchman.tools.base import Tool, ToolKind, ToolResult

# Constants
DEFAULT_FUZZ_LINES = 2
MAX_FUZZ_SEARCH_RANGE = 50


@dataclass
class PatchApplyParameters:
    """Parameters for patch application."""

    patch: str
    path: str | None = None
    dry_run: bool = False
    fuzz: int = DEFAULT_FUZZ_LINES


@dataclass
class HunkApplicationContext:
    """Context for applying a single hunk."""

    lines: list[str]
    hunk: dict[str, Any]
    hunk_idx: int
    offset: int
    fuzz: int


class HunkApplier:
    """Applies hunks to file content with fuzzy matching."""

    def apply_hunks(
        self,
        original: str,
        hunks: list[dict[str, Any]],
        fuzz: int = DEFAULT_FUZZ_LINES,
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
        lines = self._split_original_content(original)
        offset = 0

        for hunk_idx, hunk in enumerate(hunks):
            offset = self._apply_single_hunk(lines, hunk, hunk_idx, offset, fuzz)

        return self._reconstruct_content(lines, original)

    def _split_original_content(self, original: str) -> list[str]:
        """Split original content into lines, handling trailing newline.

        Args:
            original: Original file content.

        Returns:
            List of lines without trailing empty line if original had newline.
        """
        lines = original.split("\n")
        # Track if original ended with newline
        trailing_newline = original.endswith("\n")
        if trailing_newline and lines and lines[-1] == "":
            lines = lines[:-1]
        return lines

    def _reconstruct_content(self, lines: list[str], original: str) -> str:
        """Reconstruct content from lines, preserving trailing newline.

        Args:
            lines: List of content lines.
            original: Original file content for newline reference.

        Returns:
            Reconstructed content with appropriate newline.
        """
        result = "\n".join(lines)
        if original.endswith("\n"):
            result += "\n"
        return result

    def _apply_single_hunk(
        self,
        lines: list[str],
        hunk: dict[str, Any],
        hunk_idx: int,
        offset: int,
        fuzz: int,
    ) -> int:
        """Apply a single hunk to the lines and return new offset.

        Args:
            lines: Current file lines (will be modified).
            hunk: Hunk dictionary.
            hunk_idx: Index of this hunk (0-based).
            offset: Current line offset.
            fuzz: Lines of fuzz for matching.

        Returns:
            New offset after applying hunk.

        Raises:
            ValueError: If hunk fails to apply.
        """
        hunk_context = HunkApplicationContext(
            lines=lines,
            hunk=hunk,
            hunk_idx=hunk_idx,
            offset=offset,
            fuzz=fuzz,
        )
        return self._apply_hunk_with_context(hunk_context)

    def _apply_hunk_with_context(self, context: "HunkApplicationContext") -> int:
        """Apply hunk using structured context.

        Args:
            context: Hunk application context.

        Returns:
            New offset after applying hunk.

        Raises:
            ValueError: If hunk fails to apply.
        """
        old_start = int(str(context.hunk["old_start"])) - 1 + context.offset
        hunk_lines = self._extract_hunk_lines(context.hunk)
        old_lines, new_lines = self._extract_old_and_new_lines(hunk_lines)

        matched_start = self._find_match(context.lines, old_lines, old_start, context.fuzz)
        if matched_start is None:
            msg = f"Hunk {context.hunk_idx + 1} failed to apply at line {old_start + 1}"
            raise ValueError(msg)

        # Replace the old lines with new lines
        context.lines[matched_start : matched_start + len(old_lines)] = new_lines
        return context.offset + len(new_lines) - len(old_lines)

    def _extract_hunk_lines(self, hunk: dict[str, Any]) -> list[str]:
        """Extract lines from hunk dictionary."""
        lines_value = hunk.get("lines", [])
        if isinstance(lines_value, list):
            return [str(line) for line in lines_value]
        return []

    def _extract_old_and_new_lines(self, hunk_lines: list[str]) -> tuple[list[str], list[str]]:
        """Extract old and new lines from hunk lines."""
        old_lines: list[str] = []
        new_lines: list[str] = []

        for line in hunk_lines:
            if line.startswith("-"):
                old_lines.append(line[1:])
            elif line.startswith("+"):
                new_lines.append(line[1:])
            elif line.startswith(" "):
                old_lines.append(line[1:])
                new_lines.append(line[1:])

        return old_lines, new_lines

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
                    lines, old_lines, candidate,
                ):
                    return candidate

        # Wider search
        search_range = MAX_FUZZ_SEARCH_RANGE
        for start in range(
            max(0, expected_start - search_range),
            min(len(lines), expected_start + search_range),
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


class PatchParser:
    """Parser for unified diff patches."""

    def __init__(self, patch: str, default_path: str | None = None) -> None:
        """Initialize parser.

        Args:
            patch: The unified diff text.
            default_path: Default file path for headerless patches.
        """
        self.lines = patch.split("\n")
        self.default_path = default_path
        self.file_patches: dict[str, list[dict[str, Any]]] = {}
        self.current_file: str | None = default_path
        self.current_hunk: dict[str, Any] | None = None
        self.hunk_lines: list[str] = []
        self.index = 0

    def parse(self) -> dict[str, list[dict[str, Any]]]:
        """Parse the patch into file patches.

        Returns:
            Dict mapping file paths to lists of hunk dicts.

        Raises:
            ValueError: If patch is malformed.
        """
        while self.index < len(self.lines):
            self._process_line()

        self._save_current_hunk()

        if not self.file_patches and self.default_path is None:
            msg = "No file path found in patch and no default path provided"
            raise ValueError(msg)

        return self.file_patches

    def _process_line(self) -> None:
        """Process the current line."""
        line = self.lines[self.index]

        if self._is_file_header(line):
            self._handle_file_header()
        elif self._is_hunk_header(line):
            self._handle_hunk_header(line)
        elif self.current_hunk is not None:
            self._handle_hunk_content(line)
        else:
            self.index += 1

    def _is_file_header(self, line: str) -> bool:
        """Check if line is part of a file header.

        Args:
            line: The line to check.

        Returns:
            True if this is a file header line.
        """
        return (
            line.startswith("--- ")
            and self.index + 1 < len(self.lines)
            and self.lines[self.index + 1].startswith("+++ ")
        )

    def _handle_file_header(self) -> None:
        """Handle a file header section."""
        if self.default_path is None:
            path_line = self.lines[self.index + 1]
            path_str = path_line[4:].strip()
            # Strip a/ or b/ prefix
            path_str = path_str.removeprefix("b/")
            self.current_file = path_str
        self.index += 2

    def _is_hunk_header(self, line: str) -> bool:
        """Check if line is a hunk header.

        Args:
            line: The line to check.

        Returns:
            True if this is a hunk header.
        """
        return bool(re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line))

    def _handle_hunk_header(self, line: str) -> None:
        """Handle a hunk header.

        Args:
            line: The hunk header line.
        """
        self._save_current_hunk()

        hunk_data = self._parse_hunk_header(line)
        if hunk_data is None:
            return

        old_start, old_count, new_start, new_count = hunk_data

        self.current_hunk = {
            "old_start": old_start,
            "old_count": old_count,
            "new_start": new_start,
            "new_count": new_count,
        }
        self.hunk_lines = []
        self.index += 1

    def _parse_hunk_header(self, line: str) -> tuple[int, int, int, int] | None:
        """Parse hunk header line into components.

        Args:
            line: The hunk header line.
        Returns:
            Tuple of (old_start, old_count, new_start, new_count) or None if invalid.
        """
        match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
        if not match:
            return None

        old_start_str = match.group(1)
        old_count_str = match.group(2)
        new_start_str = match.group(3)
        new_count_str = match.group(4)

        old_start = int(old_start_str)
        old_count = int(old_count_str) if old_count_str else 1
        new_start = int(new_start_str)
        new_count = int(new_count_str) if new_count_str else 1

        return old_start, old_count, new_start, new_count

    def _handle_hunk_content(self, line: str) -> None:
        """Handle hunk content line.

        Args:
            line: The hunk content line.
        """
        if line.startswith(("+", "-", " ")):
            self.hunk_lines.append(line)
        elif line == "" and self.index == len(self.lines) - 1:
            pass  # trailing newline
        elif line.startswith("\\"):
            pass  # "\ No newline at end of file"

        self.index += 1

    def _save_current_hunk(self) -> None:
        """Save the current hunk if it exists."""
        if self.current_hunk is not None and self.current_file:
            self.current_hunk["lines"] = self.hunk_lines
            self.file_patches.setdefault(self.current_file, []).append(self.current_hunk)


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
                        "Target file path (required for single-file patches without file headers)"
                    ),
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "Preview changes without applying",
                    "default": False,
                },
                "fuzz": {
                    "type": "integer",
                    "description": f"Lines of fuzz for context matching (default {DEFAULT_FUZZ_LINES})",
                    "default": DEFAULT_FUZZ_LINES,
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
        fuzz: int = DEFAULT_FUZZ_LINES,
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
        params = PatchApplyParameters(
            patch=patch,
            path=path,
            dry_run=dry_run,
            fuzz=fuzz,
        )
        return await self._execute_with_params(params)

    async def _execute_with_params(self, params: PatchApplyParameters) -> ToolResult:
        """Apply patch using structured parameters."""
        if not params.patch.strip():
            return self._create_error_result("Empty patch", "Empty patch")

        try:
            file_patches = self._parse_patch(params.patch, default_path=params.path)
        except ValueError as exc:
            return self._create_error_result(f"Error parsing patch: {exc}", str(exc))

        if not file_patches:
            return self._create_error_result("Error: No hunks found in patch", "No hunks")

        results = self._apply_patches_to_files(file_patches, params.dry_run, params.fuzz)
        return self._create_result_from_application_results(results)

    def _create_error_result(self, content: str, error: str) -> ToolResult:
        """Create an error ToolResult."""
        return ToolResult(content=content, success=False, error=error)

    def _apply_patches_to_files(
        self,
        file_patches: dict[str, list[dict[str, Any]]],
        dry_run: bool,
        fuzz: int,
    ) -> list[str]:
        """Apply patches to multiple files and collect results."""
        results: list[str] = []
        for file_path, hunks in file_patches.items():
            result = self._apply_patch_to_single_file(file_path, hunks, dry_run, fuzz)
            results.append(result)
        return results

    def _apply_patch_to_single_file(
        self,
        file_path: str,
        hunks: list[dict[str, Any]],
        dry_run: bool,
        fuzz: int,
    ) -> str:
        """Apply patch to a single file and return result message."""
        target = Path(file_path)
        if not target.exists():
            return f"SKIP {file_path}: file not found"

        try:
            original = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            return f"SKIP {file_path}: {exc}"

        try:
            applier = HunkApplier()
            patched = applier.apply_hunks(original, hunks, fuzz=fuzz)
        except ValueError as exc:
            return f"FAIL {file_path}: {exc}"

        if dry_run:
            return f"OK {file_path} (dry run, {len(hunks)} hunks)"
        target.write_text(patched, encoding="utf-8")
        return f"OK {file_path} ({len(hunks)} hunks applied)"

    def _create_result_from_application_results(self, results: list[str]) -> ToolResult:
        """Create ToolResult from list of application results."""
        return ToolResult(
            content="\n".join(results),
            success=all(r.startswith("OK") for r in results),
        )

    def _parse_patch(
        self,
        patch: str,
        default_path: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Parse unified diff into file patches.

        Args:
            patch: The unified diff text.
            default_path: Default file path for headerless patches.

        Returns:
            Dict mapping file paths to lists of hunk dicts.

        Raises:
            ValueError: If patch is malformed.
        """
        parser = PatchParser(patch, default_path)
        return parser.parse()
