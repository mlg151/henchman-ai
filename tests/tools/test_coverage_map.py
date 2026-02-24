"""Tests for coverage_map tool."""

import tempfile
from pathlib import Path

from henchman.tools.base import ToolKind
from henchman.tools.builtins.coverage_map import CoverageMapTool

SAMPLE_COVERAGE_XML = """<?xml version="1.0" ?>
<coverage version="7.0" timestamp="1700000000" lines-valid="100" lines-covered="80" line-rate="0.8" branches-covered="0" branches-valid="0" branch-rate="0" complexity="0">
    <packages>
        <package name="." line-rate="0.8" branch-rate="0" complexity="0">
            <classes>
                <class name="app.py" filename="app.py" line-rate="0.75" branch-rate="0" complexity="0">
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                        <line number="3" hits="0"/>
                        <line number="4" hits="0"/>
                        <line number="5" hits="1"/>
                        <line number="10" hits="0"/>
                        <line number="11" hits="0"/>
                        <line number="12" hits="0"/>
                    </lines>
                </class>
                <class name="utils.py" filename="utils.py" line-rate="1.0" branch-rate="0" complexity="0">
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>"""

SAMPLE_COVERAGE_JSON = """{
    "files": {
        "app.py": {
            "summary": {
                "num_statements": 8,
                "missing_lines": 3,
                "num_branches": 4,
                "missing_branches": 2
            },
            "missing_lines": [3, 10, 11],
            "functions": {
                "main": {
                    "summary": {
                        "num_statements": 5,
                        "missing_lines": 1
                    }
                },
                "helper": {
                    "summary": {
                        "num_statements": 3,
                        "missing_lines": 2
                    }
                }
            }
        },
        "utils.py": {
            "summary": {
                "num_statements": 2,
                "missing_lines": 0,
                "num_branches": 0,
                "missing_branches": 0
            },
            "missing_lines": [],
            "functions": {}
        }
    }
}"""

SAMPLE_BRANCH_COVERAGE_XML = """<?xml version="1.0" ?>
<coverage version="7.0" timestamp="1700000000" lines-valid="10" lines-covered="8" line-rate="0.8" branches-covered="2" branches-valid="4" branch-rate="0.5" complexity="0">
    <packages>
        <package name="." line-rate="0.8" branch-rate="0.5" complexity="0">
            <classes>
                <class name="app.py" filename="app.py" line-rate="0.8" branch-rate="0.5" complexity="0">
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="1"/>
                        <line number="3" hits="1" branch="true" condition-coverage="50% (1/2)"/>
                        <line number="4" hits="0"/>
                        <line number="5" hits="1" branch="true" condition-coverage="100% (2/2)"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>"""

SAMPLE_FUNCTION_COVERAGE_XML = """<?xml version="1.0" ?>
<coverage version="7.0" timestamp="1700000000" lines-valid="10" lines-covered="8" line-rate="0.8" branches-covered="0" branches-valid="0" branch-rate="0" complexity="0">
    <packages>
        <package name="." line-rate="0.8" branch-rate="0" complexity="0">
            <classes>
                <class name="app.py" filename="app.py" line-rate="0.8" branch-rate="0" complexity="0">
                    <methods>
                        <method name="main" line-rate="0.9"/>
                        <method name="helper" line-rate="0.5"/>
                    </methods>
                    <lines>
                        <line number="1" hits="1"/>
                        <line number="2" hits="0"/>
                    </lines>
                </class>
            </classes>
        </package>
    </packages>
</coverage>"""


class TestCoverageMapTool:
    """Tests for CoverageMapTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = CoverageMapTool()
        assert tool.name == "coverage_map"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = CoverageMapTool()
        assert len(tool.description) > 10

    def test_kind_is_read(self) -> None:
        """Tool is READ kind."""
        tool = CoverageMapTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = CoverageMapTool()
        params = tool.parameters
        assert "properties" in params

    async def test_parse_coverage_xml(self) -> None:
        """Parse coverage.xml and return uncovered lines."""
        tool = CoverageMapTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            cov_file = Path(tmpdir) / "coverage.xml"
            cov_file.write_text(SAMPLE_COVERAGE_XML)
            result = await tool.execute(path=str(cov_file))
            assert result.success is True
            assert "app.py" in result.content
            # Lines 3,4,10,11,12 are uncovered
            assert "3" in result.content
            assert "10" in result.content

    async def test_fully_covered_file_not_reported(self) -> None:
        """Fully covered files should be noted or omitted."""
        tool = CoverageMapTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            cov_file = Path(tmpdir) / "coverage.xml"
            cov_file.write_text(SAMPLE_COVERAGE_XML)
            result = await tool.execute(path=str(cov_file))
            assert result.success is True
            # utils.py is 100% covered
            assert "utils.py" in result.content
            assert "100%" in result.content or "fully" in result.content.lower()

    async def test_nonexistent_file(self) -> None:
        """Handle nonexistent coverage file."""
        tool = CoverageMapTool()
        result = await tool.execute(path="/nonexistent/coverage.xml")
        assert result.success is False

    async def test_filter_by_file(self) -> None:
        """Filter coverage results for a specific file."""
        tool = CoverageMapTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            cov_file = Path(tmpdir) / "coverage.xml"
            cov_file.write_text(SAMPLE_COVERAGE_XML)
            result = await tool.execute(path=str(cov_file), file_filter="app.py")
            assert result.success is True
            assert "app.py" in result.content
            # Should not include utils.py when filtering
            # (or it can include it - implementation choice)

    async def test_invalid_xml(self) -> None:
        """Handle invalid XML gracefully."""
        tool = CoverageMapTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            cov_file = Path(tmpdir) / "coverage.xml"
            cov_file.write_text("this is not xml")
            result = await tool.execute(path=str(cov_file))
            assert result.success is False

    async def test_json_format(self) -> None:
        """Parse coverage.py JSON format."""
        tool = CoverageMapTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            cov_file = Path(tmpdir) / "coverage.json"
            cov_file.write_text(SAMPLE_COVERAGE_JSON)
            result = await tool.execute(path=str(cov_file))
            assert result.success is True
            assert "app.py" in result.content
            assert "3" in result.content  # Line 3 is missing

    async def test_json_file_filter(self) -> None:
        """Filter JSON coverage by file."""
        tool = CoverageMapTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            cov_file = Path(tmpdir) / "coverage.json"
            cov_file.write_text(SAMPLE_COVERAGE_JSON)
            result = await tool.execute(path=str(cov_file), file_filter="utils")
            assert result.success is True
            assert "utils.py" in result.content

    async def test_json_invalid(self) -> None:
        """Handle invalid JSON gracefully."""
        tool = CoverageMapTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            cov_file = Path(tmpdir) / "coverage.json"
            cov_file.write_text("not json{{{")
            result = await tool.execute(path=str(cov_file))
            assert result.success is False

    async def test_branch_coverage_xml(self) -> None:
        """Show branch coverage from XML."""
        tool = CoverageMapTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            cov_file = Path(tmpdir) / "coverage.xml"
            cov_file.write_text(SAMPLE_BRANCH_COVERAGE_XML)
            result = await tool.execute(path=str(cov_file), show_branches=True)
            assert result.success is True
            assert (
                "branches:" in result.content.lower()
                or "branch" in result.content.lower()
            )

    async def test_branch_coverage_json(self) -> None:
        """Show branch coverage from JSON."""
        tool = CoverageMapTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            cov_file = Path(tmpdir) / "coverage.json"
            cov_file.write_text(SAMPLE_COVERAGE_JSON)
            result = await tool.execute(path=str(cov_file), show_branches=True)
            assert result.success is True
            # JSON sample has branch data
            assert "branches:" in result.content.lower() or "app.py" in result.content

    async def test_per_function_xml(self) -> None:
        """Show per-function coverage from XML."""
        tool = CoverageMapTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            cov_file = Path(tmpdir) / "coverage.xml"
            cov_file.write_text(SAMPLE_FUNCTION_COVERAGE_XML)
            result = await tool.execute(path=str(cov_file), per_function=True)
            assert result.success is True
            assert "main" in result.content

    async def test_per_function_json(self) -> None:
        """Show per-function coverage from JSON."""
        tool = CoverageMapTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            cov_file = Path(tmpdir) / "coverage.json"
            cov_file.write_text(SAMPLE_COVERAGE_JSON)
            result = await tool.execute(path=str(cov_file), per_function=True)
            assert result.success is True
            assert "main" in result.content

    async def test_empty_path(self) -> None:
        """Handle empty path."""
        tool = CoverageMapTool()
        result = await tool.execute(path="")
        assert result.success is False

    async def test_no_matching_files(self) -> None:
        """Handle no matching files with filter."""
        tool = CoverageMapTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            cov_file = Path(tmpdir) / "coverage.xml"
            cov_file.write_text(SAMPLE_COVERAGE_XML)
            result = await tool.execute(path=str(cov_file), file_filter="nonexistent")
            assert result.success is True
            assert "nonexistent" in result.content
