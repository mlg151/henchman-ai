"""Coverage map tool implementation."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import cast

from henchman.tools.base import Tool, ToolKind, ToolResult


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
                    "description": (
                        "Optional substring filter to show only matching files"
                    ),
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

        # Detect format
        if target.suffix == ".json" or target.name.endswith(".json"):
            return self._parse_json(target, file_filter, show_branches, per_function)
        return self._parse_xml(target, file_filter, show_branches, per_function)

    def _parse_xml(
        self,
        target: Path,
        file_filter: str,
        show_branches: bool,
        per_function: bool,
    ) -> ToolResult:
        """Parse Cobertura XML format.

        Args:
            target: Path to coverage.xml file.
            file_filter: Optional filename substring filter.
            show_branches: Include branch coverage.
            per_function: Show per-function breakdown.

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
        results: list[dict[str, object]] = []

        for cls in root.iter("class"):
            filename = cls.get("filename", "")
            if file_filter and file_filter not in filename:
                continue

            line_rate = cls.get("line-rate", "0")
            branch_rate = cls.get("branch-rate", "0")

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
                # Branch coverage
                if show_branches and line.get("branch") == "true":
                    cond = line.get("condition-coverage", "")
                    if cond:
                        # Format: "50% (1/2)"
                        paren = cond.split("(")
                        if len(paren) > 1:
                            nums = paren[1].rstrip(")").split("/")
                            if len(nums) == 2:
                                covered_b = int(nums[0])
                                total_b = int(nums[1])
                                total_branches += total_b
                                missed_branches += total_b - covered_b

            entry: dict[str, object] = {
                "file": filename,
                "line_rate": line_rate,
                "total_lines": total_lines,
                "uncovered_count": len(uncovered),
                "uncovered_lines": uncovered,
            }
            if show_branches:
                entry["branch_rate"] = branch_rate
                entry["total_branches"] = total_branches
                entry["missed_branches"] = missed_branches

            # Per-function coverage from method elements
            if per_function:
                functions: list[dict[str, object]] = []
                for method in cls.iter("method"):
                    mname = method.get("name", "unknown")
                    m_line_rate = method.get("line-rate", "0")
                    functions.append({"name": mname, "line_rate": m_line_rate})
                entry["functions"] = functions

            results.append(entry)

        return self._format_results(results, show_branches, per_function, file_filter)

    def _parse_json(
        self,
        target: Path,
        file_filter: str,
        show_branches: bool,
        per_function: bool,
    ) -> ToolResult:
        """Parse coverage.py JSON format.

        Args:
            target: Path to coverage.json file.
            file_filter: Optional filename substring filter.
            show_branches: Include branch coverage.
            per_function: Show per-function breakdown.

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
        results: list[dict[str, object]] = []

        for filename, file_data in files.items():
            if file_filter and file_filter not in filename:
                continue

            summary = file_data.get("summary", {})
            total_lines = summary.get("num_statements", 0)
            missing = summary.get("missing_lines", 0)
            covered = total_lines - missing
            rate = covered / total_lines if total_lines > 0 else 1.0

            uncovered: list[int] = file_data.get("missing_lines", [])

            entry: dict[str, object] = {
                "file": filename,
                "line_rate": str(rate),
                "total_lines": total_lines,
                "uncovered_count": len(uncovered),
                "uncovered_lines": uncovered,
            }

            if show_branches:
                total_b = summary.get("num_branches", 0)
                missed_b = summary.get("missing_branches", 0)
                b_rate = (total_b - missed_b) / total_b if total_b > 0 else 1.0
                entry["branch_rate"] = str(b_rate)
                entry["total_branches"] = total_b
                entry["missed_branches"] = missed_b

            if per_function:
                functions: list[dict[str, object]] = []
                for func_name, func_data in file_data.get("functions", {}).items():
                    f_summary = func_data.get("summary", {})
                    f_total = f_summary.get("num_statements", 0)
                    f_missing = f_summary.get("missing_lines", 0)
                    f_rate = (f_total - f_missing) / f_total if f_total > 0 else 1.0
                    functions.append({"name": func_name, "line_rate": str(f_rate)})
                entry["functions"] = functions

            results.append(entry)

        return self._format_results(results, show_branches, per_function, file_filter)

    def _format_results(
        self,
        results: list[dict[str, object]],
        show_branches: bool,
        per_function: bool,
        file_filter: str,
    ) -> ToolResult:
        """Format coverage results into readable output.

        Args:
            results: List of per-file coverage data.
            show_branches: Whether branch info is included.
            per_function: Whether function breakdowns are included.
            file_filter: The filter used (for messaging).

        Returns:
            ToolResult with formatted output.
        """
        if not results:
            return ToolResult(
                content="No coverage data found"
                + (f" matching '{file_filter}'" if file_filter else ""),
                success=True,
            )

        parts: list[str] = [f"Coverage report ({len(results)} files):"]
        for entry in sorted(results, key=lambda e: str(e["file"])):
            filename = cast(str, entry["file"])
            line_rate_str = cast(str, entry["line_rate"])
            rate = float(line_rate_str) * 100
            uncovered = cast(list[int], entry["uncovered_lines"])
            total = cast(int, entry["total_lines"])

            if uncovered:
                line_ranges = self._compress_ranges(uncovered)
                line_info = (
                    f"{rate:.0f}% ({total} lines, "
                    f"{len(uncovered)} uncovered: {line_ranges})"
                )
            else:
                line_info = f"{rate:.0f}% ({total} lines, fully covered)"

            if show_branches and "branch_rate" in entry:
                b_rate = float(cast(str, entry["branch_rate"])) * 100
                total_b = cast(int, entry["total_branches"])
                missed_b = cast(int, entry["missed_branches"])
                if total_b > 0:
                    line_info += (
                        f" [branches: {b_rate:.0f}%, {missed_b}/{total_b} missed]"
                    )

            parts.append(f"  {filename}: {line_info}")

            if per_function and "functions" in entry:
                functions = cast(list[dict[str, object]], entry["functions"])
                for func in sorted(functions, key=lambda f: str(f["name"])):
                    f_rate = float(cast(str, func["line_rate"])) * 100
                    parts.append(f"    {func['name']}: {f_rate:.0f}%")

        return ToolResult(
            content="\n".join(parts),
            success=True,
        )

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
