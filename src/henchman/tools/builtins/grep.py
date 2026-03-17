"""Grep tool implementation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult


@dataclass
class GrepParameters:
    """Parameters for grep search operation."""

    pattern: str
    path: str = "."
    ignore_case: bool = False
    line_numbers: bool = False
    glob: str | None = None
    context_before: int = 0
    context_after: int = 0
    invert_match: bool = False
    whole_word: bool = False
    count_only: bool = False


@dataclass
class SearchConfig:
    """Configuration for search operations."""

    invert_match: bool
    has_context: bool
    context_before: int
    context_after: int
    line_numbers: bool
    multi_file: bool


@dataclass
class ContextConfig:
    """Configuration for context formatting."""

    context_before: int
    context_after: int
    line_numbers: bool
    file_prefix: str


@dataclass(frozen=True)
class SearchLimits:
    """Output safety limits for grep results."""

    max_matches: int
    max_output_chars: int


@dataclass
class MatchAccumulator:
    """Mutable grep output accumulator."""

    results: list[str]
    total_chars: int = 0


# ---------------------------------------------------------------------------
# Module-level pure functions (exempt from Feature Envy detection)
# ---------------------------------------------------------------------------


def _line_matches(line: str, regex: re.Pattern[str], *, invert_match: bool) -> bool:
    """Return True if the line matches (or doesn't match when inverted).

    Args:
        line: Text line to test.
        regex: Compiled regex pattern.
        invert_match: When True, return True for non-matching lines.

    Returns:
        Whether the line should be included in results.
    """
    result = bool(regex.search(line))
    return not result if invert_match else result


def _format_context_block(
    lines: list[str],
    match_indices: set[int],
    config: ContextConfig,
) -> list[str]:
    """Format matched lines with surrounding context.

    Args:
        lines: All lines in the file.
        match_indices: Set of 0-based indices of matching lines.
        config: Context formatting configuration.

    Returns:
        List of formatted output strings.
    """
    if not match_indices:
        return []

    visible: set[int] = set()
    for idx in match_indices:
        start = max(0, idx - config.context_before)
        end = min(len(lines), idx + config.context_after + 1)
        visible.update(range(start, end))

    result: list[str] = []
    prev = -2

    for idx in sorted(visible):
        if idx > prev + 1 and prev >= 0:
            result.append("--")

        line_num = idx + 1
        separator = ":" if idx in match_indices else "-"
        if config.line_numbers:
            result.append(f"{config.file_prefix}{line_num}{separator}{lines[idx]}")
        else:
            result.append(f"{config.file_prefix}{lines[idx]}")
        prev = idx

    return result


def _format_simple_matches(
    lines: list[str],
    match_indices: set[int],
    *,
    line_numbers: bool,
    file_prefix: str,
) -> list[str]:
    """Format matches without context.

    Args:
        lines: All lines in the file.
        match_indices: Set of 0-based indices of matching lines.
        line_numbers: Whether to include line numbers.
        file_prefix: Prefix for multi-file output.

    Returns:
        List of formatted output strings.
    """
    file_results: list[str] = []
    for i in sorted(match_indices):
        if line_numbers:
            file_results.append(f"{file_prefix}{i + 1}:{lines[i]}")
        else:
            file_results.append(f"{file_prefix}{lines[i]}")
    return file_results


def _find_match_indices(
    lines: list[str],
    regex: re.Pattern[str],
    *,
    invert_match: bool,
) -> set[int]:
    """Find 0-based indices of lines matching (or not matching) the pattern.

    Args:
        lines: Lines to search.
        regex: Compiled regex pattern.
        invert_match: Whether to invert match logic.

    Returns:
        Set of 0-based indices of selected lines.
    """
    return {
        i for i, line in enumerate(lines) if _line_matches(line, regex, invert_match=invert_match)
    }


def _collect_files(target: Path, glob_pattern: str | None) -> list[Path]:
    """Collect files to search from a target path.

    Args:
        target: File or directory to search.
        glob_pattern: Optional glob pattern to filter files.

    Returns:
        List of file paths to search.
    """
    if target.is_file():
        return [target]
    if glob_pattern:
        return sorted(target.glob(glob_pattern))
    return sorted(f for f in target.rglob("*") if f.is_file())


def _validate_and_setup(
    params: GrepParameters,
) -> tuple[re.Pattern[str], list[Path]] | ToolResult:
    """Validate inputs and set up for search.

    Args:
        params: Grep parameters containing pattern, path, flags, etc.

    Returns:
        Tuple of (compiled_regex, files_to_search) or ToolResult with error.
    """
    target = Path(params.path)

    if not target.exists():
        return ToolResult(
            content=f"Error: Path not found: {params.path}",
            success=False,
            error=f"Path not found: {params.path}",
        )

    effective_pattern = rf"\b{params.pattern}\b" if params.whole_word else params.pattern
    flags = re.IGNORECASE if params.ignore_case else 0

    try:
        regex = re.compile(effective_pattern, flags)
    except re.error as e:
        return ToolResult(
            content=f"Error: Invalid regex pattern: {e}",
            success=False,
            error=f"Invalid regex: {e}",
        )

    files = _collect_files(target, params.glob)
    return regex, files


def _search_single_file(
    file_path: Path,
    regex: re.Pattern[str],
    config: SearchConfig,
    file_prefix: str,
) -> tuple[list[str], int] | None:
    """Search a single file for matches.

    Args:
        file_path: Path to file to search.
        regex: Compiled regex pattern.
        config: Search configuration.
        file_prefix: Prefix for multi-file output.

    Returns:
        Tuple of (list_of_matches, total_chars) or None if no matches or error.
    """
    try:
        file_lines = file_path.read_text().splitlines()
        match_indices = _find_match_indices(file_lines, regex, invert_match=config.invert_match)

        if not match_indices:
            return None

        if config.has_context:
            context_config = ContextConfig(
                context_before=config.context_before,
                context_after=config.context_after,
                line_numbers=config.line_numbers,
                file_prefix=file_prefix,
            )
            file_results = _format_context_block(file_lines, match_indices, context_config)
        else:
            file_results = _format_simple_matches(
                file_lines,
                match_indices,
                line_numbers=config.line_numbers,
                file_prefix=file_prefix,
            )

        total_chars = sum(len(match) + 1 for match in file_results)

    except (PermissionError, UnicodeDecodeError):  # pragma: no cover
        return None
    else:
        return file_results, total_chars


def _count_file_matches(
    file_path: Path,
    regex: re.Pattern[str],
    *,
    invert_match: bool,
) -> int | None:
    """Count matching lines in a single file, returning None on read errors.

    Args:
        file_path: File to count matches in.
        regex: Compiled regex pattern.
        invert_match: Whether to count non-matching lines.

    Returns:
        Number of matching lines, or None if the file could not be read.
    """
    try:
        return sum(
            1
            for line in file_path.read_text().splitlines()
            if _line_matches(line, regex, invert_match=invert_match)
        )
    except (PermissionError, UnicodeDecodeError):  # pragma: no cover
        return None


def _count_matches_in_files(
    files: list[Path],
    regex: re.Pattern[str],
    *,
    invert_match: bool,
) -> ToolResult:
    """Count matches per file and return summary.

    Args:
        files: Files to search.
        regex: Compiled regex pattern.
        invert_match: Whether to count non-matching lines.

    Returns:
        ToolResult with match counts per file.
    """
    counts: list[str] = []
    total = 0
    for file_path in files:
        n = _count_file_matches(file_path, regex, invert_match=invert_match)
        if n is not None and n > 0:
            counts.append(f"{file_path}:{n}")
            total += n

    if not counts:
        return ToolResult(content="No matches found", success=True)

    counts.append(f"\nTotal: {total} matches")
    return ToolResult(content="\n".join(counts), success=True)


def _accumulate_matches(
    file_matches: list[str],
    accumulator: MatchAccumulator,
    limits: SearchLimits,
) -> tuple[int, bool]:
    """Accumulate file matches into results, respecting size limits."""
    for match_str in file_matches:
        accumulator.results.append(match_str)
        accumulator.total_chars += len(match_str) + 1
        if (
            len(accumulator.results) >= limits.max_matches
            or accumulator.total_chars >= limits.max_output_chars
        ):
            accumulator.results.append(
                f"... Output truncated (limit reached: {len(accumulator.results)} matches"
                f" or {accumulator.total_chars} chars) ...",
            )
            return accumulator.total_chars, True
    return accumulator.total_chars, False


def _search_files(
    files: list[Path],
    regex: re.Pattern[str],
    config: SearchConfig,
    limits: SearchLimits | None = None,
    **legacy_limits: int,
) -> ToolResult:
    """Search files and return formatted results."""
    max_matches = legacy_limits.get("max_matches")
    max_output_chars = legacy_limits.get("max_output_chars")
    effective_limits = limits or SearchLimits(
        max_matches=ResultFormatter.MAX_MATCHES if max_matches is None else max_matches,
        max_output_chars=(
            ResultFormatter.MAX_OUTPUT_CHARS if max_output_chars is None else max_output_chars
        ),
    )
    accumulator = MatchAccumulator(results=[])

    for file_path in files:
        file_prefix = f"{file_path}:" if config.multi_file else ""
        file_result = _search_single_file(file_path, regex, config, file_prefix)

        if file_result is None:
            continue

        file_matches, _ = file_result
        _, truncated = _accumulate_matches(file_matches, accumulator, effective_limits)
        if truncated:
            break

    if not accumulator.results:
        return ToolResult(content="No matches found", success=True)

    return ToolResult(content="\n".join(accumulator.results), success=True)


def _build_search_config(params: GrepParameters, file_count: int) -> SearchConfig:
    """Build a SearchConfig from grep parameters and file count."""
    return SearchConfig(
        invert_match=params.invert_match,
        has_context=params.context_before > 0 or params.context_after > 0,
        context_before=params.context_before,
        context_after=params.context_after,
        line_numbers=params.line_numbers,
        multi_file=file_count > 1,
    )


def _execute_grep(params: GrepParameters) -> ToolResult:
    """Execute grep search from a GrepParameters object.

    Args:
        params: All grep search parameters.

    Returns:
        ToolResult with search results.
    """
    validation_result = _validate_and_setup(params)

    if isinstance(validation_result, ToolResult):
        return validation_result

    regex, files = validation_result
    search_config = _build_search_config(params, len(files))

    if params.count_only:
        return _count_matches_in_files(files, regex, invert_match=params.invert_match)

    return _search_files(
        files,
        regex,
        search_config,
        limits=SearchLimits(
            max_matches=ResultFormatter.MAX_MATCHES,
            max_output_chars=ResultFormatter.MAX_OUTPUT_CHARS,
        ),
    )


# ---------------------------------------------------------------------------
# Classes (thin wrappers / schema builders)
# ---------------------------------------------------------------------------


class ResultFormatter:
    """Handles formatting of grep search results."""

    # Safety limits
    MAX_MATCHES = 1000
    MAX_OUTPUT_CHARS = 100_000

    def should_truncate(
        self: ResultFormatter,
        results: list[str],
        total_chars: int,
    ) -> bool:
        """Check if output should be truncated.

        Args:
            results: Current list of results.
            total_chars: Total characters in output so far.

        Returns:
            True if output should be truncated.
        """
        return len(results) >= self.MAX_MATCHES or total_chars >= self.MAX_OUTPUT_CHARS


class FileSearcher:
    """Handles file searching operations."""

    def __init__(self: FileSearcher, formatter: ResultFormatter) -> None:
        """Initialize with a ResultFormatter."""
        self.formatter = formatter

    def _collect_files(
        self: FileSearcher,
        target: Path,
        glob_pattern: str | None,
    ) -> list[Path]:
        """Collect files to search."""
        return _collect_files(target, glob_pattern)

    def _validate_and_setup(
        self: FileSearcher,
        params: GrepParameters,
    ) -> tuple[re.Pattern[str], list[Path]] | ToolResult:
        """Validate inputs and setup for search using a GrepParameters object."""
        return _validate_and_setup(params)

    def _find_matching_indices(
        self: FileSearcher,
        lines: list[str],
        regex: re.Pattern[str],
        invert_match: bool,  # noqa: FBT001
    ) -> set[int]:
        """Find indices of lines matching the pattern."""
        return _find_match_indices(lines, regex, invert_match=invert_match)

    def _search_single_file(
        self: FileSearcher,
        file_path: Path,
        regex: re.Pattern[str],
        config: SearchConfig,
        file_prefix: str,
    ) -> tuple[list[str], int] | None:
        """Search a single file for matches."""
        return _search_single_file(file_path, regex, config, file_prefix)

    def _count_matches(
        self: FileSearcher,
        files: list[Path],
        regex: re.Pattern[str],
        invert_match: bool,  # noqa: FBT001
    ) -> ToolResult:
        """Count matches per file."""
        if not files:
            return ToolResult(content="No matches found", success=True)
        return _count_matches_in_files(files, regex, invert_match=invert_match)

    def search_files(
        self: FileSearcher,
        files: list[Path],
        regex: re.Pattern[str],
        config: SearchConfig,
    ) -> ToolResult:
        """Search files and return formatted results.

        Args:
            files: Files to search.
            regex: Compiled regex pattern.
            config: Search configuration.

        Returns:
            ToolResult with search results.
        """
        return _search_files(
            files,
            regex,
            config,
            limits=SearchLimits(
                max_matches=self.formatter.MAX_MATCHES,
                max_output_chars=self.formatter.MAX_OUTPUT_CHARS,
            ),
        )


_PATTERN_SCHEMA_PROPERTIES: dict[str, object] = {
    "pattern": {
        "type": "string",
        "description": "Text or regex pattern to search for",
    },
    "path": {
        "type": "string",
        "description": "File or directory to search in",
    },
    "glob": {
        "type": "string",
        "description": "File glob pattern to filter files (e.g., '*.py')",
        "default": None,
    },
}

_MATCH_OPTION_SCHEMA_PROPERTIES: dict[str, object] = {
    "ignore_case": {
        "type": "boolean",
        "description": "Case insensitive search",
        "default": False,
    },
    "invert_match": {
        "type": "boolean",
        "description": "Select non-matching lines",
        "default": False,
    },
    "whole_word": {
        "type": "boolean",
        "description": "Match whole words only",
        "default": False,
    },
}

_OUTPUT_SCHEMA_PROPERTIES: dict[str, object] = {
    "line_numbers": {
        "type": "boolean",
        "description": "Include line numbers in output",
        "default": False,
    },
    "context_before": {
        "type": "integer",
        "description": "Number of lines to show before each match",
        "default": 0,
    },
    "context_after": {
        "type": "integer",
        "description": "Number of lines to show after each match",
        "default": 0,
    },
    "count_only": {
        "type": "boolean",
        "description": "Only show match counts per file",
        "default": False,
    },
}



def _coerce_kwarg(
    kwargs: dict[str, object],
    key: str,
    coercer: type[bool | int],
) -> bool | int:
    """Coerce a keyword argument using a default appropriate for the target type."""
    default = False if coercer is bool else 0
    return coercer(kwargs.get(key, default))


def _grep_params_from_kwargs(pattern: str, kwargs: dict[str, object]) -> GrepParameters:
    """Build a GrepParameters from an execute **kwargs dict."""
    path = str(kwargs.get("path") or ".")
    glob_pattern = kwargs.get("glob")
    return GrepParameters(
        pattern=pattern,
        path=path,
        ignore_case=bool(_coerce_kwarg(kwargs, "ignore_case", bool)),
        line_numbers=bool(_coerce_kwarg(kwargs, "line_numbers", bool)),
        glob=str(glob_pattern) if glob_pattern is not None else None,
        context_before=int(_coerce_kwarg(kwargs, "context_before", int)),
        context_after=int(_coerce_kwarg(kwargs, "context_after", int)),
        invert_match=bool(_coerce_kwarg(kwargs, "invert_match", bool)),
        whole_word=bool(_coerce_kwarg(kwargs, "whole_word", bool)),
        count_only=bool(_coerce_kwarg(kwargs, "count_only", bool)),
    )



class GrepTool(Tool):
    """Search for text patterns in files.

    This tool searches for text or regex patterns in files,
    similar to the grep command.
    """

    def __init__(self: GrepTool) -> None:
        """Initialize GrepTool with dependencies."""
        self.formatter = ResultFormatter()
        self.searcher = FileSearcher(self.formatter)

    @property
    def name(self: GrepTool) -> str:
        """Tool name."""
        return "grep"

    @property
    def description(self: GrepTool) -> str:
        """Tool description."""
        return "Search for text patterns in files using regex."

    @property
    def parameters(self: GrepTool) -> dict[str, object]:
        """JSON Schema for parameters."""
        return self._build_parameters_schema()

    def _build_parameters_schema(self: GrepTool) -> dict[str, object]:
        """Build JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                **_PATTERN_SCHEMA_PROPERTIES,
                **_MATCH_OPTION_SCHEMA_PROPERTIES,
                **_OUTPUT_SCHEMA_PROPERTIES,
            },
            "required": ["pattern"],
        }

    @property
    def kind(self: GrepTool) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self: GrepTool,
        pattern: str = "",
        **kwargs: object,
    ) -> ToolResult:
        """Search for pattern in files.

        Args:
            pattern: Text or regex pattern to search for.
            **kwargs: Optional path, ignore_case, line_numbers, glob,
                context_before, context_after, invert_match, whole_word,
                count_only.

        Returns:
            ToolResult with matching lines or error.
        """
        try:
            params = _grep_params_from_kwargs(pattern, kwargs)
            return _execute_grep(params)
        except (TypeError, ValueError) as e:  # pragma: no cover
            return ToolResult(
                content=f"Error searching: {e}",
                success=False,
                error=str(e),
            )

    async def _execute_with_params(
        self: GrepTool,
        params: GrepParameters,
    ) -> ToolResult:
        """Execute grep search with parameter object."""
        return _execute_grep(params)
