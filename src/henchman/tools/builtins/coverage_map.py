"""Coverage map tool implementation."""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import cast

from henchman.tools.base import Tool, ToolKind, ToolResult


class CoverageMapTool(Tool):
    """Parse coverage.xml and report uncovered lines.

    Reads a Cobertura-format coverage.xml file and extracts
    per-file information about uncovered lines.
    """

    @property
    def name(self) -> str:
        """Tool name."""
        return "coverage_map"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Parse a coverage.xml file and show uncovered lines per file. "
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
                    "description": "Path to the coverage.xml file",
                },
                "file_filter": {
                    "type": "string",
                    "description": ("Optional substring filter to show only matching files"),
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
        **kwargs: object,  # noqa: ARG002
    ) -> ToolResult:
        """Parse coverage.xml for uncovered lines.

        Args:
            path: Path to coverage.xml.
            file_filter: Optional filename substring filter.
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

        # Cobertura format: coverage > packages > package > classes > class
        for cls in root.iter("class"):
            filename = cls.get("filename", "")
            if file_filter and file_filter not in filename:
                continue

            line_rate = cls.get("line-rate", "0")

            # Find uncovered lines (hits=0)
            uncovered: list[int] = []
            total_lines = 0
            for line in cls.iter("line"):
                total_lines += 1
                hits = int(line.get("hits", "0"))
                if hits == 0:
                    line_num = int(line.get("number", "0"))
                    uncovered.append(line_num)

            results.append(
                {
                    "file": filename,
                    "line_rate": line_rate,
                    "total_lines": total_lines,
                    "uncovered_count": len(uncovered),
                    "uncovered_lines": uncovered,
                }
            )

        if not results:
            return ToolResult(
                content="No coverage data found"
                + (f" matching '{file_filter}'" if file_filter else ""),
                success=True,
            )

        # Format output
        parts: list[str] = [f"Coverage report ({len(results)} files):"]
        for entry in sorted(results, key=lambda e: str(e["file"])):
            filename = cast(str, entry["file"])
            line_rate_str = cast(str, entry["line_rate"])
            rate = float(line_rate_str) * 100
            uncovered = cast(list[int], entry["uncovered_lines"])
            total = cast(int, entry["total_lines"])

            if uncovered:
                line_ranges = self._compress_ranges(uncovered)
                parts.append(
                    f"  {filename}: {rate:.0f}% ({total} lines, "
                    f"{len(uncovered)} uncovered: {line_ranges})"
                )
            else:
                parts.append(f"  {filename}: {rate:.0f}% ({total} lines, fully covered)")

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
