"""Patch apply tool implementation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from henchman.tools.base import Tool, ToolKind, ToolResult

# Constants
DEFAULT_FUZZ_LINES = 2
MAX_FUZZ_SEARCH_RANGE = 50
_UNIFIED_DIFF_PLUS_PREFIX_LEN = 4  # Length of the "+++ " or "--- " header prefix

_HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))?"
    r" \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@",
)

_PATCH_APPLY_PARAMETERS: dict[str, object] = {
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


@dataclass
class FilePatchRequest:
    """Request to apply a patch to a single file."""

    file_path: str
    hunks: list[dict[str, Any]]
    dry_run: bool
    fuzz: int


# ---------------------------------------------------------------------------
# Module-level pure helpers (no class context -- avoid Feature Envy)
# ---------------------------------------------------------------------------


def _split_original_content(original: str) -> list[str]:
    """Split original content into lines, stripping a trailing empty entry."""
    lines = original.split("\n")
    if original.endswith("\n") and lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def _reconstruct_content(lines: list[str], original: str) -> str:
    """Reconstruct content from lines, preserving trailing newline."""
    result = "\n".join(lines)
    if original.endswith("\n"):
        result += "\n"
    return result


def _extract_hunk_lines(hunk: dict[str, Any]) -> list[str]:
    """Extract lines from a hunk dictionary."""
    lines_value = hunk.get("lines", [])
    if isinstance(lines_value, list):
        return [str(line) for line in lines_value]
    return []


def _classify_hunk_line(line: str) -> tuple[list[str], list[str]]:
    """Return (old_contributions, new_contributions) for a single hunk line."""
    content = line[1:]
    if line.startswith("-"):
        return [content], []
    if line.startswith("+"):
        return [], [content]
    if line.startswith(" "):
        return [content], [content]
    return [], []


def _extract_old_and_new_lines(
    hunk_lines: list[str],
) -> tuple[list[str], list[str]]:
    """Extract old (removed) and new (added) lines from raw hunk lines."""
    old_lines: list[str] = []
    new_lines: list[str] = []
    for line in hunk_lines:
        old_contrib, new_contrib = _classify_hunk_line(line)
        old_lines.extend(old_contrib)
        new_lines.extend(new_contrib)
    return old_lines, new_lines


def _lines_match(lines: list[str], old_lines: list[str], start: int) -> bool:
    """Return True if old_lines match lines at position start."""
    if start < 0 or start + len(old_lines) > len(lines):
        return False
    return lines[start : start + len(old_lines)] == old_lines


def _find_match(
    lines: list[str],
    old_lines: list[str],
    expected_start: int,
    fuzz: int,
) -> int | None:
    """Find where old_lines match in lines, with fuzzy search around expected_start."""
    if not old_lines:
        return max(0, min(expected_start, len(lines)))
    if _lines_match(lines, old_lines, expected_start):
        return expected_start
    for delta in range(1, fuzz + 1):
        for candidate in [expected_start - delta, expected_start + delta]:
            if 0 <= candidate <= len(lines) - len(old_lines) and _lines_match(
                lines,
                old_lines,
                candidate,
            ):
                return candidate
    for start in range(
        max(0, expected_start - MAX_FUZZ_SEARCH_RANGE),
        min(len(lines), expected_start + MAX_FUZZ_SEARCH_RANGE),
    ):
        if _lines_match(lines, old_lines, start):
            return start
    return None


def _apply_hunk_with_context(context: HunkApplicationContext) -> int:
    """Apply a single hunk and return the new cumulative line offset."""
    old_start = int(str(context.hunk["old_start"])) - 1 + context.offset
    hunk_lines = _extract_hunk_lines(context.hunk)
    old_lines, new_lines = _extract_old_and_new_lines(hunk_lines)
    matched_start = _find_match(context.lines, old_lines, old_start, context.fuzz)
    if matched_start is None:
        msg = f"Hunk {context.hunk_idx + 1} failed to apply at line {old_start + 1}"
        raise ValueError(msg)
    context.lines[matched_start : matched_start + len(old_lines)] = new_lines
    return context.offset + len(new_lines) - len(old_lines)


def _parse_hunk_header(line: str) -> tuple[int, int, int, int] | None:
    """Parse a unified-diff hunk header into (old_start, old_count, new_start, new_count)."""
    match = _HUNK_HEADER_RE.match(line)
    if not match:
        return None
    old_start = int(match.group("old_start"))
    old_count = int(match.group("old_count") or "1")
    new_start = int(match.group("new_start"))
    new_count = int(match.group("new_count") or "1")
    return old_start, old_count, new_start, new_count


def _apply_patch_to_single_file(request: FilePatchRequest) -> str:
    """Apply patch hunks to one file and return a status message."""
    target = Path(request.file_path)
    if not target.exists():
        return f"SKIP {request.file_path}: file not found"
    try:
        original = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"SKIP {request.file_path}: {exc}"
    try:
        applier = HunkApplier(fuzz=request.fuzz)
        patched = applier.apply_hunks(original, request.hunks)
    except ValueError as exc:
        return f"FAIL {request.file_path}: {exc}"
    if request.dry_run:
        return f"OK {request.file_path} (dry run, {len(request.hunks)} hunks)"
    target.write_text(patched, encoding="utf-8")
    return f"OK {request.file_path} ({len(request.hunks)} hunks applied)"


def _apply_patches_to_files(
    file_patches: dict[str, list[dict[str, Any]]],
    *,
    dry_run: bool,
    fuzz: int,
) -> list[str]:
    """Apply patches to all files and return status messages."""
    return [
        _apply_patch_to_single_file(
            FilePatchRequest(file_path=fp, hunks=hunks, dry_run=dry_run, fuzz=fuzz),
        )
        for fp, hunks in file_patches.items()
    ]


def _build_patch_params_from_kwargs(kwargs: dict[str, object]) -> PatchApplyParameters:
    """Build a PatchApplyParameters from raw **kwargs.

    Kept at module level so Feature Envy is not triggered on execute().

    Args:
        kwargs: Raw keyword arguments from execute(**kwargs).

    Returns:
        Populated PatchApplyParameters.
    """
    return PatchApplyParameters(
        patch=str(kwargs.get("patch", "")),
        path=str(kwargs["path"]) if kwargs.get("path") is not None else None,
        dry_run=bool(kwargs.get("dry_run", False)),
        fuzz=int(kwargs.get("fuzz", DEFAULT_FUZZ_LINES)),
    )


class HunkApplier:
    """Applies hunks to file content with fuzzy matching."""

    # Expose module-level helpers as static methods for backward compatibility.
    _split_original_content = staticmethod(_split_original_content)
    _reconstruct_content = staticmethod(_reconstruct_content)
    _extract_hunk_lines = staticmethod(_extract_hunk_lines)
    _extract_old_and_new_lines = staticmethod(_extract_old_and_new_lines)
    _find_match = staticmethod(_find_match)
    _lines_match = staticmethod(_lines_match)

    def __init__(self: HunkApplier, fuzz: int = DEFAULT_FUZZ_LINES) -> None:
        """Initialise with the desired fuzz factor for context matching."""
        self.fuzz = fuzz

    def apply_hunks(
        self: HunkApplier,
        original: str,
        hunks: list[dict[str, Any]],
    ) -> str:
        """Apply hunks to original content and return the patched text.

        Args:
            original: Original file content.
            hunks: List of hunk dicts.

        Returns:
            Patched file content.

        Raises:
            ValueError: If a hunk fails to apply.
        """
        lines = self._split_original_content(original)
        offset = 0
        for hunk_idx, hunk in enumerate(hunks):
            context = HunkApplicationContext(
                lines=lines,
                hunk=hunk,
                hunk_idx=hunk_idx,
                offset=offset,
                fuzz=self.fuzz,
            )
            offset = _apply_hunk_with_context(context)
        return self._reconstruct_content(lines, original)


class PatchParser:
    """Parser for unified diff patches."""

    # Provide instance access for backward compatibility.
    _parse_hunk_header = staticmethod(_parse_hunk_header)

    def __init__(self: PatchParser, patch: str, default_path: str | None = None) -> None:
        """Initialise parser.

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

    def parse(self: PatchParser) -> dict[str, list[dict[str, Any]]]:
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

    def _process_line(self: PatchParser) -> None:
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

    def _is_file_header(self: PatchParser, line: str) -> bool:
        """Return True if line starts a file header (--- / +++ pair)."""
        return (
            line.startswith("--- ")
            and self.index + 1 < len(self.lines)
            and self.lines[self.index + 1].startswith("+++ ")
        )

    def _handle_file_header(self: PatchParser) -> None:
        """Consume a file header and update current_file."""
        if self.default_path is None:
            path_line = self.lines[self.index + 1]
            path_str = path_line[_UNIFIED_DIFF_PLUS_PREFIX_LEN:].strip()
            path_str = path_str.removeprefix("b/")
            self.current_file = path_str
        self.index += 2

    def _is_hunk_header(self: PatchParser, line: str) -> bool:
        """Return True if line is a hunk header (@@ ... @@)."""
        return bool(_HUNK_HEADER_RE.match(line))

    def _handle_hunk_header(self: PatchParser, line: str) -> None:
        """Save the current hunk and start a new one from line."""
        self._save_current_hunk()

        hunk_data = _parse_hunk_header(line)
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

    def _handle_hunk_content(self: PatchParser, line: str) -> None:
        """Append a diff content line to hunk_lines."""
        if line.startswith(("+", "-", " ")):
            self.hunk_lines.append(line)
        self.index += 1

    def _save_current_hunk(self: PatchParser) -> None:
        """Persist current_hunk into file_patches if one is active."""
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
    def name(self: PatchApplyTool) -> str:
        """Tool name."""
        return "patch_apply"

    @property
    def description(self: PatchApplyTool) -> str:
        """Tool description."""
        return (
            "Apply a unified diff patch to one or more files. "
            "Supports multi-hunk patches, dry-run preview, and "
            "fuzzy context matching."
        )

    @property
    def parameters(self: PatchApplyTool) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {**_PATCH_APPLY_PARAMETERS}

    @property
    def kind(self: PatchApplyTool) -> ToolKind:
        """Tool kind - WRITE because it modifies files."""
        return ToolKind.WRITE

    async def execute(  # type: ignore[override]
        self: PatchApplyTool,
        **kwargs: object,
    ) -> ToolResult:
        """Apply a unified diff patch.

        Args:
            **kwargs: patch, path, dry_run, fuzz -- see tool parameters.

        Returns:
            ToolResult with application status.
        """
        return await self._execute_with_params(_build_patch_params_from_kwargs(kwargs))

    async def _execute_with_params(
        self: PatchApplyTool,
        params: PatchApplyParameters,
    ) -> ToolResult:
        """Apply patch using structured parameters."""
        if not params.patch.strip():
            return self._create_error_result("Empty patch", "Empty patch")

        try:
            file_patches = self._parse_patch(params.patch, default_path=params.path)
        except ValueError as exc:
            return self._create_error_result(f"Error parsing patch: {exc}", str(exc))

        if not file_patches:
            return self._create_error_result("Error: No hunks found in patch", "No hunks")

        results = _apply_patches_to_files(
            file_patches,
            dry_run=params.dry_run,
            fuzz=params.fuzz,
        )
        return self._create_result_from_application_results(results)

    def _create_error_result(
        self: PatchApplyTool,
        content: str,
        error: str,
    ) -> ToolResult:
        """Create an error ToolResult."""
        return ToolResult(content=content, success=False, error=error)

    def _create_result_from_application_results(
        self: PatchApplyTool,
        results: list[str],
    ) -> ToolResult:
        """Create ToolResult from list of application results."""
        return ToolResult(
            content="\n".join(results),
            success=all(r.startswith("OK") for r in results),
        )

    def _parse_patch(
        self: PatchApplyTool,
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

    def _apply_patch_to_single_file(
        self: PatchApplyTool,
        file_path: str,
        hunks: list[dict[str, Any]],
        *,
        dry_run: bool = False,
        fuzz: int = DEFAULT_FUZZ_LINES,
    ) -> str:
        """Apply patch to a single file — thin shim for backward compatibility."""
        return _apply_patch_to_single_file(
            FilePatchRequest(file_path=file_path, hunks=hunks, dry_run=dry_run, fuzz=fuzz),
        )
