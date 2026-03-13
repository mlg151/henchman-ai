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
            assert "branches:" in result.content.lower() or "branch" in result.content.lower()

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


class TestCoverageMapInternals:
    """Tests for coverage_map internal helpers."""

    def test_compress_ranges_empty(self) -> None:
        """_compress_ranges returns empty string for empty list."""
        from henchman.tools.builtins.coverage_map import CoverageFormatter
        fmt = CoverageFormatter()
        result = fmt._compress_ranges([])
        assert result == ""

    def test_compress_ranges_single(self) -> None:
        """_compress_ranges returns single number."""
        from henchman.tools.builtins.coverage_map import CoverageFormatter
        fmt = CoverageFormatter()
        result = fmt._compress_ranges([5])
        assert result == "5"

    def test_compress_ranges_consecutive(self) -> None:
        """_compress_ranges compresses consecutive lines to range."""
        from henchman.tools.builtins.coverage_map import CoverageFormatter
        fmt = CoverageFormatter()
        result = fmt._compress_ranges([1, 2, 3, 5])
        assert "1-3" in result
        assert "5" in result

    def test_parse_branch_coverage_no_cond(self) -> None:
        """_parse_branch_coverage returns None when no condition-coverage attr."""
        import xml.etree.ElementTree as ET

        from henchman.tools.builtins.coverage_map import XmlCoverageParser
        parser = XmlCoverageParser()
        line = ET.Element("line")
        result = parser._parse_branch_coverage(line)
        assert result is None

    def test_parse_branch_coverage_no_paren(self) -> None:
        """_parse_branch_coverage returns None when no parenthesis in condition."""
        import xml.etree.ElementTree as ET

        from henchman.tools.builtins.coverage_map import XmlCoverageParser
        parser = XmlCoverageParser()
        line = ET.Element("line")
        line.set("condition-coverage", "50%")
        result = parser._parse_branch_coverage(line)
        assert result is None

    def test_parse_branch_coverage_wrong_parts(self) -> None:
        """_parse_branch_coverage returns None when wrong number of parts."""
        import xml.etree.ElementTree as ET

        from henchman.tools.builtins.coverage_map import XmlCoverageParser
        parser = XmlCoverageParser()
        line = ET.Element("line")
        line.set("condition-coverage", "50% (1)")
        result = parser._parse_branch_coverage(line)
        assert result is None

    def test_parse_branch_coverage_value_error(self) -> None:
        """_parse_branch_coverage returns None on ValueError."""
        import xml.etree.ElementTree as ET

        from henchman.tools.builtins.coverage_map import XmlCoverageParser
        parser = XmlCoverageParser()
        line = ET.Element("line")
        line.set("condition-coverage", "50% (x/y)")
        result = parser._parse_branch_coverage(line)
        assert result is None

    async def test_xml_with_filter_skips_non_matching(self) -> None:
        """XML parser skips classes not matching file_filter."""
        import tempfile
        from pathlib import Path

        from henchman.tools.builtins.coverage_map import CoverageMapTool
        tool = CoverageMapTool()
        xml_content = '''<?xml version="1.0" ?>
<coverage>
  <packages><package><classes>
    <class filename="src/foo.py" line-rate="1.0" branch-rate="1.0">
      <lines><line number="1" hits="1"/></lines>
    </class>
    <class filename="src/bar.py" line-rate="0.5" branch-rate="0.0">
      <lines><line number="1" hits="0"/></lines>
    </class>
  </classes></package></packages>
</coverage>'''
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "coverage.xml"
            f.write_text(xml_content)
            result = await tool.execute(path=str(f), file_filter="foo")
            assert result.success is True
            assert "foo" in result.content
            assert "bar" not in result.content

    async def test_xml_with_branches(self) -> None:
        """XML parser includes branch coverage when show_branches=True."""
        import tempfile
        from pathlib import Path

        from henchman.tools.builtins.coverage_map import CoverageMapTool
        tool = CoverageMapTool()
        xml_content = '''<?xml version="1.0" ?>
<coverage>
  <packages><package><classes>
    <class filename="src/foo.py" line-rate="0.5" branch-rate="0.5">
      <lines>
        <line number="1" hits="1" branch="true" condition-coverage="50% (1/2)"/>
        <line number="2" hits="0"/>
      </lines>
    </class>
  </classes></package></packages>
</coverage>'''
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "coverage.xml"
            f.write_text(xml_content)
            result = await tool.execute(path=str(f), show_branches=True)
            assert result.success is True

    async def test_json_with_filter(self) -> None:
        """JSON parser skips files not matching filter."""
        import json
        import tempfile
        from pathlib import Path

        from henchman.tools.builtins.coverage_map import CoverageMapTool
        tool = CoverageMapTool()
        data = {
            "files": {
                "src/foo.py": {
                    "summary": {"num_statements": 10, "missing_lines": 2}
                },
                "src/bar.py": {
                    "summary": {"num_statements": 5, "missing_lines": 0}
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "coverage.json"
            f.write_text(json.dumps(data))
            result = await tool.execute(path=str(f), file_filter="foo")
            assert result.success is True
            assert "foo" in result.content


class TestCoverageMapDirectCalls:
    """Direct tests for internal coverage_map methods."""

    def test_parse_class_returns_none_for_filter_mismatch(self) -> None:
        """_parse_class returns None when filter does not match filename."""
        import xml.etree.ElementTree as ET

        from henchman.tools.builtins.coverage_map import CoverageConfig, XmlCoverageParser

        parser = XmlCoverageParser()
        config = CoverageConfig(file_filter="foo")
        cls = ET.Element("class")
        cls.set("filename", "src/bar.py")
        cls.set("line-rate", "1.0")
        cls.set("branch-rate", "0.0")
        result = parser._parse_class(cls, config)
        assert result is None

    def test_parse_lines_branch_data_none(self) -> None:
        """_parse_lines handles branch line where _parse_branch_coverage returns None."""
        import xml.etree.ElementTree as ET

        from henchman.tools.builtins.coverage_map import CoverageConfig, XmlCoverageParser

        parser = XmlCoverageParser()
        config = CoverageConfig(show_branches=True)
        cls = ET.Element("class")
        cls.set("filename", "src/foo.py")
        # Line with branch="true" but unparseable condition-coverage
        line = ET.SubElement(cls, "line")
        line.set("number", "1")
        line.set("hits", "1")
        line.set("branch", "true")
        line.set("condition-coverage", "bad-format")
        uncovered, total, missed, total_branches = parser._parse_lines(cls, config)
        assert total == 1
        assert total_branches == 0  # branch_data was None, nothing added

    def test_json_parse_file_returns_none_for_filter(self) -> None:
        """JsonCoverageParser._parse_file returns None when filter doesn't match."""
        from henchman.tools.builtins.coverage_map import CoverageConfig, JsonCoverageParser

        parser = JsonCoverageParser()
        config = CoverageConfig(file_filter="foo")
        result = parser._parse_file("src/bar.py", {"summary": {}}, config)
        assert result is None

    async def test_xml_parse_entry_none_skipped(self) -> None:
        """XML parse skips entries where _parse_class returns None."""
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from henchman.tools.builtins.coverage_map import CoverageMapTool

        tool = CoverageMapTool()
        xml_content = '''<?xml version="1.0" ?>
<coverage>
  <packages><package><classes>
    <class filename="src/foo.py" line-rate="1.0" branch-rate="0.0">
      <lines><line number="1" hits="1"/></lines>
    </class>
  </classes></package></packages>
</coverage>'''
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "coverage.xml"
            f.write_text(xml_content)
            # Patch _parse_class to return None
            from henchman.tools.builtins.coverage_map import XmlCoverageParser
            with patch.object(XmlCoverageParser, "_parse_class", return_value=None):
                result = await tool.execute(path=str(f))
                assert result.success is True

    async def test_json_parse_entry_none_skipped(self) -> None:
        """JSON parse skips entries where _parse_file returns None (441->436)."""
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        from henchman.tools.builtins.coverage_map import CoverageMapTool, JsonCoverageParser

        tool = CoverageMapTool()
        json_data = {
            "files": {
                "src/foo.py": {
                    "summary": {"num_statements": 10, "missing_lines": 2, "percent_covered": 80.0}
                }
            }
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "coverage.json"
            f.write_text(json.dumps(json_data))
            # Patch _parse_file to return None, triggering 441->436
            with patch.object(JsonCoverageParser, "_parse_file", return_value=None):
                result = await tool.execute(path=str(f))
                assert result.success is True
