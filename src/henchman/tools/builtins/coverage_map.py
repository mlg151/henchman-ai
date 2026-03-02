"""Coverage map tool implementation."""

import json
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from henchman.tools.base import Tool, ToolKind, ToolResult


@dataclass
class CoverageConfig:
    """Configuration for coverage parsing operations."""

    file_filter: str = ""
    show_branches: bool = False
    per_function: bool = False

    def has_filter(self) -> bool:
        """Check if a file filter is active."""
        return bool(self.file_filter.strip())


@dataclass
class CoverageRequest:
    """Request parameters for coverage analysis."""

    path: str
    file_filter: str = ""
    show_branches: bool = False
    per_function: bool = False

    def to_config(self) -> CoverageConfig:
        """Convert request to configuration object."""
        return CoverageConfig(
            file_filter=self.file_filter,
            show_branches=self.show_branches,
            per_function=self.per_function,
        )


class CoverageFormatter:
    """Formats coverage results into readable output."""

    @staticmethod
    def format_results(
        results: list[dict[str, Any]],
        config: CoverageConfig,
    ) -> ToolResult:
        """Format coverage results into readable output.

        Args:
            results: List of per-file coverage data.
            config: Coverage parsing configuration.

        Returns:
            ToolResult with formatted output.
        """
        if not results:
            return ToolResult(
                content="No coverage data found"
                + (f" matching '{config.file_filter}'" if config.has_filter() else ""),
                success=True,
            )

        parts: list[str] = [f"Coverage report ({len(results)} files):"]
        for entry in sorted(results, key=lambda e: str(e["file"])):
            CoverageFormatter._format_file_entry(entry, parts, config)

        return ToolResult(
            content="\n".join(parts),
            success=True,
        )

    @staticmethod
    def _format_file_entry(
        entry: dict[str, Any],
        parts: list[str],
        config: CoverageConfig,
    ) -> None:
        """Format a single file entry for output.

        Args:
            entry: File coverage data dictionary.
            parts: List to append formatted lines to.
            config: Coverage parsing configuration.
        """
        filename = cast(str, entry["file"])
        line_rate_str = cast(str, entry["line_rate"])
        rate = float(line_rate_str) * 100
        uncovered = cast(list[int], entry["uncovered_lines"])
        total = cast(int, entry["total_lines"])

        line_info = CoverageFormatter._format_coverage_line(rate, total, uncovered)

        if config.show_branches and "branch_rate" in entry:
            line_info += CoverageFormatter._format_branch_info(entry)

        parts.append(f"  {filename}: {line_info}")

        if config.per_function and "functions" in entry:
            CoverageFormatter._format_function_info(entry, parts)

    @staticmethod
    def _format_coverage_line(
        rate: float,
        total: int,
        uncovered: list[int],
    ) -> str:
        """Format the main coverage line.

        Args:
            rate: Coverage percentage (0-100).
            total: Total number of lines.
            uncovered: List of uncovered line numbers.

        Returns:
            Formatted coverage line string.
        """
        if uncovered:
            line_ranges = CoverageFormatter._compress_ranges(uncovered)
            return f"{rate:.0f}% ({total} lines, {len(uncovered)} uncovered: {line_ranges})"
        else:
            return f"{rate:.0f}% ({total} lines, fully covered)"

    @staticmethod
    def _format_branch_info(
        entry: dict[str, Any],
    ) -> str:
        """Format branch coverage information.

        Args:
            entry: File coverage data dictionary.

        Returns:
            Formatted branch info string.
        """
        b_rate = float(cast(str, entry["branch_rate"])) * 100
        total_b = cast(int, entry["total_branches"])
        missed_b = cast(int, entry["missed_branches"])

        if total_b > 0:
            return f" [branches: {b_rate:.0f}%, {missed_b}/{total_b} missed]"
        return ""

    @staticmethod
    def _format_function_info(
        entry: dict[str, Any],
        parts: list[str],
    ) -> None:
        """Format per-function coverage information.

        Args:
            entry: File coverage data dictionary.
            parts: List to append formatted lines to.
        """
        functions = cast(list[dict[str, Any]], entry["functions"])
        for func in sorted(functions, key=lambda f: str(f["name"])):
            f_rate = float(cast(str, func["line_rate"])) * 100
            parts.append(f"    {func['name']}: {f_rate:.0f}%")

    @staticmethod
    def _compress_ranges(lines: list[int]) -> str:
        """Compress line numbers into ranges.

        Args:
            lines: Sorted list of line numbers.

        Returns:
            String like "1-3, 5, 7-10".
        """
        if not lines:
            return ""

        sorted_lines = sorted(lines)
        ranges: list[str] = []
        start = sorted_lines[0]
        end = start

        for line in sorted_lines[1:]:
            if line == end + 1:
                end = line
            else:
                ranges.append(f"{start}-{end}" if start != end else str(start))
                start = line
                end = line

        ranges.append(f"{start}-{end}" if start != end else str(start))
        return ", ".join(ranges)


class BaseCoverageParser(ABC):
    """Base class for coverage parsers with common functionality."""

    def __init__(self, formatter: CoverageFormatter | None = None):
        """Initialize parser with optional formatter.

        Args:
            formatter: Formatter instance, uses default if None.
        """
        self.formatter = formatter or CoverageFormatter()

    @abstractmethod
    def parse(self, target: Path, config: CoverageConfig) -> ToolResult:
        """Parse coverage file.

        Args:
            target: Path to coverage file.
            config: Coverage parsing configuration.

        Returns:
            ToolResult with coverage information.
        """
        pass

    @staticmethod
    def _parse_branch_coverage(
        line: ET.Element,
    ) -> tuple[int, int] | None:
        """Parse branch coverage data from line element.

        Args:
            line: XML line element with branch data.

        Returns:
            Tuple of (covered_branches, total_branches) or None if invalid.
        """
        cond = line.get("condition-coverage", "")
        if not cond:
            return None

        # Format: "50% (1/2)"
        paren = cond.split("(")
        if len(paren) <= 1:
            return None

        nums = paren[1].rstrip(")").split("/")
        if len(nums) != 2:
            return None

        try:
            covered_b = int(nums[0])
            total_b = int(nums[1])
            return covered_b, total_b
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_functions_from_xml(
        cls: ET.Element,
    ) -> list[dict[str, str]]:
        """Parse function/method elements from XML class.

        Args:
            cls: XML class element.

        Returns:
            List of function dictionaries with name and line_rate.
        """
        functions: list[dict[str, str]] = []
        for method in cls.iter("method"):
            mname = method.get("name", "unknown")
            m_line_rate = method.get("line-rate", "0")
            functions.append({"name": mname, "line_rate": m_line_rate})
        return functions

    @staticmethod
    def _parse_functions_from_json(
        file_data: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Parse function data from JSON file coverage.

        Args:
            file_data: File coverage data dictionary.

        Returns:
            List of function dictionaries with name and line_rate.
        """
        functions: list[dict[str, str]] = []
        for func_name, func_data in file_data.get("functions", {}).items():
            f_summary = func_data.get("summary", {})
            f_total = f_summary.get("num_statements", 0)
            f_missing = f_summary.get("missing_lines", 0)
            f_rate = (f_total - f_missing) / f_total if f_total > 0 else 1.0
            functions.append({"name": func_name, "line_rate": str(f_rate)})
        return functions


class XmlCoverageParser(BaseCoverageParser):
    """Parser for Cobertura XML coverage format."""

    def parse(self, target: Path, config: CoverageConfig) -> ToolResult:
        """Parse Cobertura XML format.

        Args:
            target: Path to coverage.xml file.
            config: Coverage parsing configuration.

        Returns:
            ToolResult with coverage information.
        """
        try:
            tree = ET.parse(str(target))  # noqa: S314
        except ET.ParseError as exc:
            return ToolResult(
                content=f"Error parsing XML: {exc}",
                success=False,
                error=str(exc),
            )

        root = tree.getroot()
        results: list[dict[str, Any]] = []

        for cls in root.iter("class"):
            filename = cls.get("filename", "")
            if config.has_filter() and config.file_filter not in filename:
                continue

            entry = self._parse_class(cls, config)
            if entry:
                results.append(entry)

        return self.formatter.format_results(results, config)

    def _parse_class(
        self,
        cls: ET.Element,
        config: CoverageConfig,
    ) -> dict[str, Any] | None:
        """Parse a single class element from XML coverage.

        Args:
            cls: XML class element.
            config: Coverage parsing configuration.

        Returns:
            Dictionary with coverage data or None if filtered out.
        """
        filename = cls.get("filename", "")
        if config.has_filter() and config.file_filter not in filename:
            return None

        line_rate = cls.get("line-rate", "0")
        branch_rate = cls.get("branch-rate", "0")

        uncovered_lines, total_lines, missed_branches, total_branches = self._parse_lines(
            cls, config
        )

        entry: dict[str, Any] = {
            "file": filename,
            "line_rate": line_rate,
            "total_lines": total_lines,
            "uncovered_count": len(uncovered_lines),
            "uncovered_lines": uncovered_lines,
        }

        if config.show_branches:
            entry["branch_rate"] = branch_rate
            entry["total_branches"] = total_branches
            entry["missed_branches"] = missed_branches

        if config.per_function:
            entry["functions"] = self._parse_functions_from_xml(cls)

        return entry

    def _parse_lines(
        self,
        cls: ET.Element,
        config: CoverageConfig,
    ) -> tuple[list[int], int, int, int]:
        """Parse line elements from XML class.

        Args:
            cls: XML class element.
            config: Coverage parsing configuration.

        Returns:
            Tuple of (uncovered_lines, total_lines, missed_branches, total_branches)
        """
        uncovered: list[int] = []
        total_lines = 0
        missed_branches = 0
        total_branches = 0

        for line in cls.iter("line"):
            total_lines += 1
            hits = int(line.get("hits", "0"))
            if hits == 0:
                line_num = int(line.get("number", "0"))
                uncovered.append(line_num)

            if config.show_branches and line.get("branch") == "true":
                branch_data = self._parse_branch_coverage(line)
                if branch_data:
                    covered_b, total_b = branch_data
                    total_branches += total_b
                    missed_branches += total_b - covered_b

        return uncovered, total_lines, missed_branches, total_branches


class JsonCoverageParser(BaseCoverageParser):
    """Parser for coverage.py JSON format."""
    """Parser for coverage.py JSON format."""

    def parse(self, target: Path, config: CoverageConfig) -> ToolResult:
        """Parse coverage.py JSON format.

        Args:
            target: Path to coverage.json file.
            config: Coverage parsing configuration.

        Returns:
            ToolResult with coverage information.
        """
        try:
            data = json.loads(target.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return ToolResult(
                content=f"Error parsing JSON: {exc}",
                success=False,
                error=str(exc),
            )

        files = data.get("files", {})
        results: list[dict[str, Any]] = []

        for filename, file_data in files.items():
            if config.has_filter() and config.file_filter not in filename:
                continue

            entry = self._parse_file(filename, file_data, config)
            if entry:
                results.append(entry)

        return self._format_results(results, config)

    def _parse_file(
        self,
        filename: str,
        file_data: dict[str, Any],
        config: CoverageConfig,
    ) -> dict[str, Any] | None:
        """Parse a single file from JSON coverage data.

        Args:
            filename: Name of the file.
            file_data: File coverage data dictionary.
            config: Coverage parsing configuration.

        Returns:
            Dictionary with coverage data or None if filtered out.
        """
        if config.has_filter() and config.file_filter not in filename:
            return None

        summary = file_data.get("summary", {})
        total_lines = summary.get("num_statements", 0)
        missing = summary.get("missing_lines", 0)
        covered = total_lines - missing
        rate = covered / total_lines if total_lines > 0 else 1.0

        uncovered: list[int] = file_data.get("missing_lines", [])

        entry: dict[str, Any] = {
            "file": filename,
            "line_rate": str(rate),
            "total_lines": total_lines,
            "uncovered_count": len(uncovered),
            "uncovered_lines": uncovered,
        }

        if config.show_branches:
            self._add_branch_coverage(entry, summary)

        if config.per_function:
            entry["functions"] = self._parse_functions(file_data)

        return entry

    def _add_branch_coverage(
        self,
        entry: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        """Add branch coverage data to entry from JSON summary.

        Args:
            entry: Coverage entry dictionary to update.
            summary: JSON summary dictionary.
        """
        total_b = summary.get("num_branches", 0)
        missed_b = summary.get("missing_branches", 0)
        b_rate = (total_b - missed_b) / total_b if total_b > 0 else 1.0
        entry["branch_rate"] = str(b_rate)
        entry["total_branches"] = total_b
        entry["missed_branches"] = missed_b

    def _parse_functions(
        self,
        file_data: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Parse function data from JSON file coverage.

        Args:
            file_data: File coverage data dictionary.

        Returns:
            List of function dictionaries with name and line_rate.
        """
        functions: list[dict[str, str]] = []
        for func_name, func_data in file_data.get("functions", {}).items():
            f_summary = func_data.get("summary", {})
            f_total = f_summary.get("num_statements", 0)
            f_missing = f_summary.get("missing_lines", 0)
            f_rate = (f_total - f_missing) / f_total if f_total > 0 else 1.0
            functions.append({"name": func_name, "line_rate": str(f_rate)})
        return functions

    def _format_results(
        self,
        results: list[dict[str, Any]],
        config: CoverageConfig,
    ) -> ToolResult:
        """Format coverage results into readable output.

        Args:
            results: List of per-file coverage data.
            config: Coverage parsing configuration.

        Returns:
            ToolResult with formatted output.
        """
        if not results:
            return ToolResult(
                content="No coverage data found"
                + (f" matching '{config.file_filter}'" if config.has_filter() else ""),
                success=True,
            )

        parts: list[str] = [f"Coverage report ({len(results)} files):"]
        for entry in sorted(results, key=lambda e: str(e["file"])):
            self._format_file_entry(entry, parts, config)

        return ToolResult(
            content="\n".join(parts),
            success=True,
        )

    def _format_file_entry(
        self,
        entry: dict[str, Any],
        parts: list[str],
        config: CoverageConfig,
    ) -> None:
        """Format a single file entry for output.

        Args:
            entry: File coverage data dictionary.
            parts: List to append formatted lines to.
            config: Coverage parsing configuration.
        """
        filename = cast(str, entry["file"])
        line_rate_str = cast(str, entry["line_rate"])
        rate = float(line_rate_str) * 100
        uncovered = cast(list[int], entry["uncovered_lines"])
        total = cast(int, entry["total_lines"])

        line_info = self._format_coverage_line(rate, total, uncovered)

        if config.show_branches and "branch_rate" in entry:
            line_info += self._format_branch_info(entry)

        parts.append(f"  {filename}: {line_info}")

        if config.per_function and "functions" in entry:
            self._format_function_info(entry, parts)

    def _format_coverage_line(
        self,
        rate: float,
        total: int,
        uncovered: list[int],
    ) -> str:
        """Format the main coverage line.

        Args:
            rate: Coverage percentage (0-100).
            total: Total number of lines.
            uncovered: List of uncovered line numbers.

        Returns:
            Formatted coverage line string.
        """
        if uncovered:
            line_ranges = self._compress_ranges(uncovered)
            return f"{rate:.0f}% ({total} lines, {len(uncovered)} uncovered: {line_ranges})"
        else:
            return f"{rate:.0f}% ({total} lines, fully covered)"

    def _format_branch_info(
        self,
        entry: dict[str, Any],
    ) -> str:
        """Format branch coverage information.

        Args:
            entry: File coverage data dictionary.

        Returns:
            Formatted branch info string.
        """
        b_rate = float(cast(str, entry["branch_rate"])) * 100
        total_b = cast(int, entry["total_branches"])
        missed_b = cast(int, entry["missed_branches"])

        if total_b > 0:
            return f" [branches: {b_rate:.0f}%, {missed_b}/{total_b} missed]"
        return ""

    def _format_function_info(
        self,
        entry: dict[str, Any],
        parts: list[str],
    ) -> None:
        """Format per-function coverage information.

        Args:
            entry: File coverage data dictionary.
            parts: List to append formatted lines to.
        """
        functions = cast(list[dict[str, Any]], entry["functions"])
        for func in sorted(functions, key=lambda f: str(f["name"])):
            f_rate = float(cast(str, func["line_rate"])) * 100
            parts.append(f"    {func['name']}: {f_rate:.0f}%")

    def _compress_ranges(self, lines: list[int]) -> str:
        """Compress line numbers into ranges.

        Args:
            lines: Sorted list of line numbers.

        Returns:
            String like "1-3, 5, 7-10".
        """
        if not lines:
            return ""

        sorted_lines = sorted(lines)
        ranges: list[str] = []
        start = sorted_lines[0]
        end = start

        for line in sorted_lines[1:]:
            if line == end + 1:
                end = line
            else:
                ranges.append(f"{start}-{end}" if start != end else str(start))
                start = line
                end = line

        ranges.append(f"{start}-{end}" if start != end else str(start))
        return ", ".join(ranges)


class CoverageMapTool(Tool):
    """Parse coverage reports and show uncovered lines.

    Reads Cobertura-format coverage.xml or coverage.py JSON (.coverage)
    files and extracts per-file information about uncovered lines,
    branch coverage, and per-function statistics.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "coverage_map"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Parse a coverage report (XML or JSON) and show uncovered lines "
            "per file. Supports branch coverage and per-function stats. "
            "Useful for identifying untested code paths."
        )

    @property
    def parameters(self) -> dict[str, object]:
        """JSON Schema for parameters."""
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to coverage.xml or coverage.json file",
                },
                "file_filter": {
                    "type": "string",
                    "description": ("Optional substring filter to show only matching files"),
                },
                "show_branches": {
                    "type": "boolean",
                    "description": "Include branch coverage information",
                    "default": False,
                },
                "per_function": {
                    "type": "boolean",
                    "description": "Show per-function coverage breakdown",
                    "default": False,
                },
            },
            "required": ["path"],
        }

    @property
    def kind(self) -> ToolKind:
        """Tool kind - read-only analysis."""
        return ToolKind.READ

    async def execute(  # type: ignore[override]
        self,
        path: str = "",
        file_filter: str = "",
        show_branches: bool = False,
        per_function: bool = False,
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Parse coverage report for uncovered lines.

        Args:
            path: Path to coverage.xml or coverage.json.
            file_filter: Optional filename substring filter.
            show_branches: Include branch coverage in output.
            per_function: Show per-function coverage breakdown.
            **kwargs: Additional arguments (ignored).

        Returns:
            ToolResult with coverage information.
        """
        request = CoverageRequest(
            path=path,
            file_filter=file_filter,
            show_branches=show_branches,
            per_function=per_function,
        )

        if not request.path:
            return ToolResult(
                content="Error: No path provided",
                success=False,
                error="Empty path",
            )

        target = Path(request.path)
        if not target.exists():
            return ToolResult(
                content=f"Error: File not found: {request.path}",
                success=False,
                error=f"File not found: {request.path}",
            )

        config = request.to_config()

        # Detect format and use appropriate parser
        if target.suffix == ".json" or target.name.endswith(".json"):
            parser = JsonCoverageParser()
        else:
            parser = XmlCoverageParser()

        return parser.parse(target, config)
