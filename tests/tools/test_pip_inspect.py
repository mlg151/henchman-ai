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
        assert "henchman-ai" in result.content.lower()

    async def test_inspect_specific_package(self) -> None:
        """Inspect a specific installed package."""
        tool = PipInspectTool()
        result = await tool.execute(package="henchman-ai")
        assert result.success is True
        assert "henchman-ai" in result.content.lower()
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

    async def test_pip_error_message(self) -> None:
        """Returns error when pip fails."""
        from unittest.mock import AsyncMock, MagicMock, patch

        tool = PipInspectTool()
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"ERROR: some pip error"))
        mock_process.returncode = 1
        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await tool.execute()
            assert result.success is False
            assert "ERROR" in result.content or "error" in result.content.lower()

    async def test_output_truncation(self) -> None:
        """Large output is truncated."""
        from unittest.mock import AsyncMock, MagicMock, patch

        tool = PipInspectTool()
        large_output = ("package==1.0.0\n" * 10000).encode()
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(large_output, b""))
        mock_process.returncode = 0
        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await tool.execute()
            assert result.success is True
            assert "truncated" in result.content

    async def test_empty_output_no_packages(self) -> None:
        """Empty stdout with success returns no packages message (line 93)."""
        from unittest.mock import AsyncMock, MagicMock, patch

        tool = PipInspectTool()
        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0
        with patch("asyncio.create_subprocess_exec", return_value=mock_process):
            result = await tool.execute()
            assert result.success is True
            assert "No packages" in result.content

    async def test_falls_back_to_metadata_without_pip(self) -> None:
        """A seedless virtual environment remains inspectable."""
        from unittest.mock import AsyncMock, patch

        with patch(
            "henchman.tools.builtins.pip_inspect._run_pip_command",
            new=AsyncMock(return_value=(b"", b"No module named pip", 1)),
        ):
            listed = await PipInspectTool().execute()
            inspected = await PipInspectTool().execute(package="henchman-ai")
            missing = await PipInspectTool().execute(package="nonexistent_fake_package_xyz")

        assert listed.success is True
        assert "henchman-ai" in listed.content.lower()
        assert inspected.success is True
        assert "Version:" in inspected.content
        assert missing.success is False
