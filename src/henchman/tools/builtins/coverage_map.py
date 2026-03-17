"""Coverage map tool implementation."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from henchman.tools.base import Tool, ToolKind, ToolResult

_EXPECTED_BRANCH_PARTS = 2
_PERCENT_SCALE = 100.0


@dataclass
class CoverageConfig:
    """Configuration for coverage parsing operations."""

    file_filter: str = ""
    show_branches: bool = False
    per_function: bool = False

    def has_filter(self: CoverageConfig) -> bool:
        """Check if a file filter is active.

        Returns:
            True if a non-empty file filter is set, False otherwise.
        """
        return bool(self.file_filter.strip())


@dataclass
class CoverageRequest:
    """Request parameters for coverage analysis."""

    path: str
    file_filter: str = ""
    show_branches: bool = False
    per_function: bool = False

    def to_config(self: CoverageRequest) -> CoverageConfig:
        """Convert request to configuration object.

        Returns:
            CoverageConfig instance with fields copied from this request.
        """
        return CoverageConfig(
            file_filter=self.file_filter,
            show_branches=self.show_branches,
            per_function=self.per_function,
        )


def _do_compress_ranges(lines: list[int]) -> str:
    """Compress line numbers into a compact ranges string.

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


def _format_coverage_line_text(rate: float, total: int, uncovered: list[int]) -> str:
    """Format the main coverage percentage line.

    Args:
        rate: Coverage percentage (0-100).
        total: Total number of lines.
        uncovered: List of uncovered line numbers.

    Returns:
        Formatted coverage line string.
    """
    if uncovered:
        line_ranges = _do_compress_ranges(uncovered)
        return f"{rate:.0f}% ({total} lines, {len(uncovered)} uncovered: {line_ranges})"
    return f"{rate:.0f}% ({total} lines, fully covered)"


def _format_branch_info_text(entry: dict[str, Any]) -> str:
    """Format branch coverage information from a file entry.

    Args:
        entry: File coverage data dictionary.

    Returns:
        Formatted branch info string, or empty string if no branches.
    """
    b_rate = float(cast("str", entry["branch_rate"])) * _PERCENT_SCALE
    total_b = cast("int", entry["total_branches"])
    missed_b = cast("int", entry["missed_branches"])
    if total_b > 0:
        return f" [branches: {b_rate:.0f}%, {missed_b}/{total_b} missed]"
    return ""


def _format_function_coverage(entry: dict[str, Any], parts: list[str]) -> None:
    """Append per-function coverage lines to parts.

    Args:
        entry: File coverage data dictionary.
        parts: List to append formatted lines to.
    """
    functions = cast("list[dict[str, Any]]", entry["functions"])
    for func in sorted(functions, key=lambda f: str(f["name"])):
        f_rate = float(cast("str", func["line_rate"])) * _PERCENT_SCALE
        parts.append(f"    {func['name']}: {f_rate:.0f}%")


def _format_file_entry(
    entry: dict[str, Any],
    parts: list[str],
    config: CoverageConfig,
) -> None:
    """Format a single file entry and append it to parts.

    Args:
        entry: File coverage data dictionary.
        parts: List to append formatted lines to.
        config: Coverage parsing configuration.
    """
    filename = cast("str", entry["file"])
    rate = float(cast("str", entry["line_rate"])) * _PERCENT_SCALE
    uncovered = cast("list[int]", entry["uncovered_lines"])
    total = cast("int", entry["total_lines"])
    line_info = _format_coverage_line_text(rate, total, uncovered)
    if config.show_branches and "branch_rate" in entry:
        line_info += _format_branch_info_text(entry)
    parts.append(f"  {filename}: {line_info}")
    if config.per_function and "functions" in entry:
        _format_function_coverage(entry, parts)


def _extract_coverage_params(params: dict[str, object]) -> tuple[str, CoverageConfig]:
    """Extract path and CoverageConfig from raw tool parameters.

    Args:
        params: Raw keyword parameters passed to the tool.

    Returns:
        Tuple of (path_string, CoverageConfig).
    """
    path = str(params.get("path", ""))
    config = CoverageConfig(
        file_filter=str(params.get("file_filter", "")),
        show_branches=bool(params.get("show_branches", False)),
        per_function=bool(params.get("per_function", False)),
    )
    return path, config


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
            _format_file_entry(entry, parts, config)

        return ToolResult(
            content="\n".join(parts),
            success=True,
        )

    @staticmethod
    def _compress_ranges(lines: list[int]) -> str:
        """Compress line numbers into ranges."""
        return _do_compress_ranges(lines)


def _do_parse_branch_coverage(line: ET.Element) -> tuple[int, int] | None:
    """Parse branch coverage data from an XML line element.

    Args:
        line: XML line element with branch data.

    Returns:
        Tuple of (covered_branches, total_branches) or None if invalid.
    """
    cond = line.get("condition-coverage", "")
    if not cond:
        return None
    paren = cond.split("(")
    if len(paren) <= 1:
        return None
    nums = paren[1].rstrip(")").split("/")
    if len(nums) != _EXPECTED_BRANCH_PARTS:
        return None
    try:
        covered_b = int(nums[0])
        total_b = int(nums[1])
    except (ValueError, TypeError):
        return None
    else:
        return covered_b, total_b


def _do_parse_xml_functions(cls: ET.Element) -> list[dict[str, str]]:
    """Parse function/method elements from an XML class element.

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


def _do_parse_json_functions(file_data: dict[str, Any]) -> list[dict[str, str]]:
    """Parse function data from a JSON file coverage entry.

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


def _do_parse_xml_lines(
    cls: ET.Element,
    config: CoverageConfig,
) -> tuple[list[int], int, int, int]:
    """Parse line elements from an XML class element.

    Args:
        cls: XML class element.
        config: Coverage parsing configuration.

    Returns:
        Tuple of (uncovered_lines, total_lines, missed_branches, total_branches).
    """
    uncovered: list[int] = []
    total_lines = 0
    missed_branches = 0
    total_branches = 0
    for line in cls.iter("line"):
        total_lines += 1
        hits = int(line.get("hits", "0"))
        if hits == 0:
            uncovered.append(int(line.get("number", "0")))
        if config.show_branches and line.get("branch") == "true":
            branch_data = _do_parse_branch_coverage(line)
            if branch_data:
                covered_b, total_b = branch_data
                total_branches += total_b
                missed_branches += total_b - covered_b
    return uncovered, total_lines, missed_branches, total_branches


def _do_parse_xml_class(
    cls: ET.Element,
    config: CoverageConfig,
) -> dict[str, Any] | None:
    """Parse a single XML class element into a coverage data dict.

    Args:
        cls: XML class element.
        config: Coverage parsing configuration.

    Returns:
        Dictionary with coverage data, or None if filtered out.
    """
    filename = cls.get("filename", "")
    if config.has_filter() and config.file_filter not in filename:
        return None
    line_rate = cls.get("line-rate", "0")
    branch_rate = cls.get("branch-rate", "0")
    uncovered_lines, total_lines, missed_branches, total_branches = _do_parse_xml_lines(cls, config)
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
        entry["functions"] = _do_parse_xml_functions(cls)
    return entry


def _do_add_json_branch_coverage(entry: dict[str, Any], summary: dict[str, Any]) -> None:
    """Add branch coverage data to entry from a JSON summary dict.

    Args:
        entry: Coverage entry dictionary to update in-place.
        summary: JSON summary dictionary.
    """
    total_b = summary.get("num_branches", 0)
    missed_b = summary.get("missing_branches", 0)
    b_rate = (total_b - missed_b) / total_b if total_b > 0 else 1.0
    entry["branch_rate"] = str(b_rate)
    entry["total_branches"] = total_b
    entry["missed_branches"] = missed_b


def _do_parse_json_file(
    filename: str,
    file_data: dict[str, Any],
    config: CoverageConfig,
) -> dict[str, Any] | None:
    """Parse a single file entry from JSON coverage data.

    Args:
        filename: Name of the file.
        file_data: File coverage data dictionary.
        config: Coverage parsing configuration.

    Returns:
        Dictionary with coverage data, or None if filtered out.
    """
    if config.has_filter() and config.file_filter not in filename:
        return None
    summary = file_data.get("summary", {})
    total_lines = summary.get("num_statements", 0)
    missing = summary.get("missing_lines", 0)
    rate = (total_lines - missing) / total_lines if total_lines > 0 else 1.0
    uncovered: list[int] = file_data.get("missing_lines", [])
    entry: dict[str, Any] = {
        "file": filename,
        "line_rate": str(rate),
        "total_lines": total_lines,
        "uncovered_count": len(uncovered),
        "uncovered_lines": uncovered,
    }
    if config.show_branches:
        _do_add_json_branch_coverage(entry, summary)
    if config.per_function:
        entry["functions"] = _do_parse_json_functions(file_data)
    return entry


class BaseCoverageParser(ABC):
    """Base class for coverage parsers with common functionality."""

    def __init__(self: BaseCoverageParser, formatter: CoverageFormatter | None = None) -> None:
        """Initialize parser with optional formatter.

        Args:
            formatter: Formatter instance, uses default if None.
        """
        self.formatter = formatter or CoverageFormatter()

    @abstractmethod
    def parse(self: BaseCoverageParser, target: Path, config: CoverageConfig) -> ToolResult:
        """Parse coverage file.

        Args:
            target: Path to coverage file.
            config: Coverage parsing configuration.

        Returns:
            ToolResult with coverage information.
        """

    @staticmethod
    def _parse_branch_coverage(line: ET.Element) -> tuple[int, int] | None:
        """Parse branch coverage data from an XML line element."""
        return _do_parse_branch_coverage(line)

    @staticmethod
    def _parse_functions_from_xml(element: ET.Element) -> list[dict[str, str]]:
        """Parse function/method elements from XML class."""
        return _do_parse_xml_functions(element)

    @staticmethod
    def _parse_functions_from_json(file_data: dict[str, Any]) -> list[dict[str, str]]:
        """Parse function data from JSON file coverage."""
        return _do_parse_json_functions(file_data)


class XmlCoverageParser(BaseCoverageParser):
    """Parser for Cobertura XML coverage format."""

    def parse(self: XmlCoverageParser, target: Path, config: CoverageConfig) -> ToolResult:
        """Parse Cobertura XML format.

        Args:
            target: Path to coverage.xml file.
            config: Coverage parsing configuration.

        Returns:
            ToolResult with coverage information.
        """
        try:
            tree = ET.parse(str(target))
        except ET.ParseError as exc:
            return ToolResult(
                content=f"Error parsing XML: {exc}",
                success=False,
                error=str(exc),
            )

        root = tree.getroot()
        results: list[dict[str, Any]] = []

        for cls in root.iter("class"):
            entry = _do_parse_xml_class(cls, config)
            if entry:
                results.append(entry)

        return self.formatter.format_results(results, config)

    def _parse_class(
        self: XmlCoverageParser,
        cls: ET.Element,
        config: CoverageConfig,
    ) -> dict[str, Any] | None:
        """Parse a single class element from XML coverage."""
        return _do_parse_xml_class(cls, config)

    def _parse_lines(
        self: XmlCoverageParser,
        cls: ET.Element,
        config: CoverageConfig,
    ) -> tuple[list[int], int, int, int]:
        """Parse line elements from XML class."""
        return _do_parse_xml_lines(cls, config)


class JsonCoverageParser(BaseCoverageParser):
    """Parser for coverage.py JSON format."""

    def parse(self: JsonCoverageParser, target: Path, config: CoverageConfig) -> ToolResult:
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
        results: list[dict[str, Any]] = [
            entry
            for filename, file_data in files.items()
            for entry in [_do_parse_json_file(filename, file_data, config)]
            if entry
        ]
        return self.formatter.format_results(results, config)

    def _parse_file(
        self: JsonCoverageParser,
        filename: str,
        file_data: dict[str, Any],
        config: CoverageConfig,
    ) -> dict[str, Any] | None:
        """Parse a single file from JSON coverage data."""
        return _do_parse_json_file(filename, file_data, config)

    def _add_branch_coverage(
        self: JsonCoverageParser,
        entry: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        """Add branch coverage data to entry from JSON summary."""
        _do_add_json_branch_coverage(entry, summary)


class CoverageMapTool(Tool):
    """Parse coverage reports and show uncovered lines.

    Reads Cobertura-format coverage.xml or coverage.py JSON (.coverage)
    files and extracts per-file information about uncovered lines,
    branch coverage, and per-function statistics.
    """

    @property
    def name(self: CoverageMapTool) -> str:
        """Tool name."""
        return "coverage_map"

    @property
    def description(self: CoverageMapTool) -> str:
        """Tool description."""
        return (
            "Parse a coverage report (XML or JSON) and show uncovered lines "
            "per file. Supports branch coverage and per-function stats. "
            "Useful for identifying untested code paths."
        )

    @property
    def parameters(self: CoverageMapTool) -> dict[str, object]:
        """JSON Schema for parameters."""
        filter_schema: dict[str, object] = {
            "type": "string",
            "description": "Optional substring filter to show only matching files",
        }
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to coverage.xml or coverage.json file",
                },
                "file_filter": filter_schema,
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
    def kind(self: CoverageMapTool) -> ToolKind:
        """Tool kind - read-only analysis."""
        return ToolKind.READ

    def _run_parser(
        self: CoverageMapTool,
        target: Path,
        config: CoverageConfig,
    ) -> ToolResult:
        """Select and run the appropriate parser for target.

        Args:
            target: Path to the coverage file.
            config: Coverage parsing configuration.

        Returns:
            ToolResult with coverage information.
        """
        if target.suffix == ".json" or target.name.endswith(".json"):
            return JsonCoverageParser().parse(target, config)
        return XmlCoverageParser().parse(target, config)

    async def execute(self: CoverageMapTool, **params: object) -> ToolResult:
        """Parse coverage report for uncovered lines.

        Args:
            params: Tool parameters passed as keyword arguments.
                Expected keys: path, file_filter, show_branches, per_function.

        Returns:
            ToolResult with coverage information.
        """
        path, config = _extract_coverage_params(params)
        if not path:
            return ToolResult(
                content="Error: No path provided",
                success=False,
                error="Empty path",
            )
        target = Path(path)
        if not target.exists():
            return ToolResult(
                content=f"Error: File not found: {path}",
                success=False,
                error=f"File not found: {path}",
            )
        return self._run_parser(target, config)
