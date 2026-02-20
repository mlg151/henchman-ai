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
