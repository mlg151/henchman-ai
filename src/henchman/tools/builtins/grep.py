"""Grep tool implementation."""

import re
from pathlib import Path

from henchman.tools.base import Tool, ToolKind, ToolResult


class GrepTool(Tool):
    """Search for text patterns in files.

    This tool searches for text or regex patterns in files,
    similar to the grep command.
    """

    # Safety limits
    MAX_MATCHES = 1000
    MAX_OUTPUT_CHARS = 100_000

    @property
    def name(self) -> str:
        """Tool name."""
        return "grep"

    @property
    def description(self) -> str:
        """Tool description."""
        return "Search for text patterns in files using regex."

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Text or regex pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "File or directory to search in",
                },
                "ignore_case": {
                    "type": "boolean",
                    "description": "Case insensitive search",
                    "default": False,
                },
                "line_numbers": {
                    "type": "boolean",
                    "description": "Include line numbers in output",
                    "default": False,
                },
                "glob": {
                    "type": "string",
                    "description": "File glob pattern to filter files (e.g., '*.py')",
                    "default": None,
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
                "count_only": {
                    "type": "boolean",
                    "description": "Only show match counts per file",
                    "default": False,
                },
            },
            "required": ["pattern"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - READ is auto-approved."""
        return ToolKind.READ

    def _collect_files(self, target: Path, glob_pattern: str | None) -> list[Path]:
        """Collect files to search.

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

    def _format_context_block(
        self,
        lines: list[str],
        match_indices: set[int],
        context_before: int,
        context_after: int,
        line_numbers: bool,
        file_prefix: str,
    ) -> list[str]:
        """Format matched lines with surrounding context.

        Args:
            lines: All lines in the file.
            match_indices: Set of 0-based indices of matching lines.
            context_before: Number of context lines before match.
            context_after: Number of context lines after match.
            line_numbers: Whether to include line numbers.
            file_prefix: Prefix for multi-file output (e.g., "path/file.py:").

        Returns:
            List of formatted output strings.
        """
        if not match_indices:
            return []

        # Build set of all lines to show (matches + context)
        visible: set[int] = set()
        for idx in match_indices:
            start = max(0, idx - context_before)
            end = min(len(lines), idx + context_after + 1)
            visible.update(range(start, end))

        result: list[str] = []
        sorted_visible = sorted(visible)
        prev = -2

        for idx in sorted_visible:
            # Insert separator between non-contiguous blocks
            if idx > prev + 1 and prev >= 0:
                result.append("--")

            line_num = idx + 1
            separator = ":" if idx in match_indices else "-"
            if line_numbers:
                result.append(f"{file_prefix}{line_num}{separator}{lines[idx]}")
            else:
                result.append(f"{file_prefix}{lines[idx]}")
            prev = idx

        return result

    async def execute(  # type: ignore[override]
        self,
        pattern: str = "",
        path: str = ".",
        ignore_case: bool = False,
        line_numbers: bool = False,
        glob: str | None = None,
        context_before: int = 0,
        context_after: int = 0,
        invert_match: bool = False,
        whole_word: bool = False,
        count_only: bool = False,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Search for pattern in files.

        Args:
            pattern: Text or regex pattern to search for.
            path: File or directory to search in.
            ignore_case: Case insensitive search.
            line_numbers: Include line numbers in output.
            glob: File glob pattern to filter files.
            context_before: Lines of context before each match.
            context_after: Lines of context after each match.
            invert_match: Select non-matching lines.
            whole_word: Match whole words only.
            count_only: Only show match counts per file.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with matching lines or error.
        """
        try:
            # Validate and setup
            validation_result = self._validate_and_setup(
                pattern=pattern,
                path=path,
                ignore_case=ignore_case,
                whole_word=whole_word,
                glob=glob,
            )

            # Check if validation returned an error
            if isinstance(validation_result, ToolResult):
                return validation_result

            regex, files = validation_result
            has_context = context_before > 0 or context_after > 0
            multi_file = len(files) > 1

            # Count-only mode
            if count_only:
                return self._count_matches(files, regex, invert_match)

            # Search files
            return self._search_files_with_results(
                files=files,
                regex=regex,
                invert_match=invert_match,
                has_context=has_context,
                context_before=context_before,
                context_after=context_after,
                line_numbers=line_numbers,
                multi_file=multi_file,
            )
        except Exception as e:  # pragma: no cover
            return ToolResult(
                content=f"Error searching: {e}",
                success=False,
                error=str(e),
            )

    def _count_matches(
        self,
        files: list[Path],
        regex: re.Pattern[str],
        invert_match: bool,
    ) -> ToolResult:
        """Count matches per file.

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
            try:
                content = file_path.read_text()
                n = 0
                for line in content.splitlines():
                    is_match = bool(regex.search(line))
                    if invert_match:
                        is_match = not is_match
                    if is_match:
                        n += 1
                if n > 0:
                    counts.append(f"{file_path}:{n}")
                    total += n
            except (PermissionError, UnicodeDecodeError):  # pragma: no cover
                continue

        if not counts:
            return ToolResult(content="No matches found", success=True)

        counts.append(f"\nTotal: {total} matches")
        return ToolResult(content="\n".join(counts), success=True)

    def _validate_and_setup(
        self,
        pattern: str,
        path: str,
        ignore_case: bool,
        whole_word: bool,
        glob: str | None = None,
    ) -> tuple[re.Pattern[str], list[Path]] | ToolResult:
        """Validate inputs and setup for search.

        Args:
            pattern: Text or regex pattern to search for.
            path: File or directory to search in.
            ignore_case: Case insensitive search.
            whole_word: Match whole words only.
            glob: File glob pattern to filter files.

        Returns:
            Tuple of (compiled_regex, files_to_search) or ToolResult with error.
        """
        target = Path(path)

        if not target.exists():
            return ToolResult(
                content=f"Error: Path not found: {path}",
                success=False,
                error=f"Path not found: {path}",
            )

        # Wrap pattern for whole-word matching
        effective_pattern = rf"\b{pattern}\b" if whole_word else pattern

        # Compile regex
        flags = re.IGNORECASE if ignore_case else 0
        try:
            regex = re.compile(effective_pattern, flags)
        except re.error as e:
            return ToolResult(
                content=f"Error: Invalid regex pattern: {e}",
                success=False,
                error=f"Invalid regex: {e}",
            )

        files = self._collect_files(target, glob)
        return regex, files

    def _search_files_with_results(
        self,
        files: list[Path],
        regex: re.Pattern[str],
        invert_match: bool,
        has_context: bool,
        context_before: int,
        context_after: int,
        line_numbers: bool,
        multi_file: bool,
    ) -> ToolResult:
        """Search files and return formatted results.

        Args:
            files: Files to search.
            regex: Compiled regex pattern.
            invert_match: Whether to invert match logic.
            has_context: Whether to show context lines.
            context_before: Lines of context before each match.
            context_after: Lines of context after each match.
            line_numbers: Whether to include line numbers.
            multi_file: Whether searching multiple files.

        Returns:
            ToolResult with search results.
        """
        results: list[str] = []
        total_chars = 0
        truncated = False

        for file_path in files:
            if truncated:
                break

            file_result = self._search_single_file(
                file_path=file_path,
                regex=regex,
                invert_match=invert_match,
                has_context=has_context,
                context_before=context_before,
                context_after=context_after,
                line_numbers=line_numbers,
                multi_file=multi_file,
            )

            if file_result is None:
                continue  # File had no matches or couldn't be read

            file_matches, file_chars = file_result

            # Add file results with truncation check
            for match_str in file_matches:
                results.append(match_str)
                total_chars += len(match_str) + 1

                if self._should_truncate(results, total_chars):
                    truncated = True
                    results.append(
                        f"... Output truncated (limit reached: {len(results)} matches"
                        f" or {total_chars} chars) ..."
                    )
                    break

            if truncated:
                break

        if not results:
            return ToolResult(
                content="No matches found",
                success=True,
            )

        return ToolResult(
            content="\n".join(results),
            success=True,
        )

    def _search_single_file(
        self,
        file_path: Path,
        regex: re.Pattern[str],
        invert_match: bool,
        has_context: bool,
        context_before: int,
        context_after: int,
        line_numbers: bool,
        multi_file: bool,
    ) -> tuple[list[str], int] | None:
        """Search a single file for matches.

        Args:
            file_path: Path to file to search.
            regex: Compiled regex pattern.
            invert_match: Whether to invert match logic.
            has_context: Whether to show context lines.
            context_before: Lines of context before each match.
            context_after: Lines of context after each match.
            line_numbers: Whether to include line numbers.
            multi_file: Whether searching multiple files.

        Returns:
            Tuple of (list_of_matches, total_chars) or None if no matches or error.
        """
        try:
            content = file_path.read_text()
            file_lines = content.splitlines()
            file_prefix = f"{file_path}:" if multi_file else ""

            # Find matching line indices
            match_indices = self._find_matching_indices(file_lines, regex, invert_match)

            if not match_indices:
                return None

            # Format results
            if has_context:
                file_results = self._format_context_block(
                    file_lines,
                    match_indices,
                    context_before,
                    context_after,
                    line_numbers,
                    file_prefix,
                )
            else:
                file_results = self._format_simple_matches(
                    file_lines, match_indices, line_numbers, file_prefix
                )

            total_chars = sum(len(match) + 1 for match in file_results)
            return file_results, total_chars

        except (PermissionError, UnicodeDecodeError):  # pragma: no cover
            return None

    def _find_matching_indices(
        self,
        lines: list[str],
        regex: re.Pattern[str],
        invert_match: bool,
    ) -> set[int]:
        """Find indices of lines matching the pattern.

        Args:
            lines: Lines to search.
            regex: Compiled regex pattern.
            invert_match: Whether to invert match logic.

        Returns:
            Set of 0-based indices of matching lines.
        """
        match_indices: set[int] = set()
        for i, line in enumerate(lines):
            is_match = bool(regex.search(line))
            if invert_match:
                is_match = not is_match
            if is_match:
                match_indices.add(i)
        return match_indices

    def _format_simple_matches(
        self,
        lines: list[str],
        match_indices: set[int],
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

    def _should_truncate(self, results: list[str], total_chars: int) -> bool:
        """Check if output should be truncated.

        Args:
            results: Current list of results.
            total_chars: Total characters in output so far.

        Returns:
            True if output should be truncated.
        """
        return (
            len(results) >= self.MAX_MATCHES
            or total_chars >= self.MAX_OUTPUT_CHARS
        )
