"""Tests for pip_inspect tool."""

from henchman.tools.base import ToolKind
from henchman.tools.builtins.pip_inspect import PipInspectTool


class TestPipInspectTool:
    """Tests for PipInspectTool."""

    def test_name(self) -> None:
        """Tool has correct name."""
        tool = PipInspectTool()
        assert tool.name == "pip_inspect"

    def test_description(self) -> None:
        """Tool has a description."""
        tool = PipInspectTool()
        assert len(tool.description) > 10

    def test_kind_is_read(self) -> None:
        """Tool is READ kind."""
        tool = PipInspectTool()
        assert tool.kind == ToolKind.READ

    def test_parameters_schema(self) -> None:
        """Tool has correct parameters schema."""
        tool = PipInspectTool()
        params = tool.parameters
        assert "properties" in params

    async def test_list_packages(self) -> None:
        """List installed packages."""
        tool = PipInspectTool()
        result = await tool.execute()
        assert result.success is True
        # pip itself should be present
        assert "pip" in result.content.lower()

    async def test_inspect_specific_package(self) -> None:
        """Inspect a specific installed package."""
        tool = PipInspectTool()
        result = await tool.execute(package="pip")
        assert result.success is True
        assert "pip" in result.content.lower()
        # Should include version info
        assert "version" in result.content.lower() or "." in result.content

    async def test_inspect_nonexistent_package(self) -> None:
        """Handle nonexistent package."""
        tool = PipInspectTool()
        result = await tool.execute(package="nonexistent_fake_package_xyz")
        assert result.success is False

    async def test_list_includes_versions(self) -> None:
        """Package listing includes version numbers."""
        tool = PipInspectTool()
        result = await tool.execute()
        assert result.success is True
        # Should have at least some version-like strings
        assert "." in result.content
