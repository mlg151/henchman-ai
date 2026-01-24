"""Tests for ExtensionManager."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from henchman.cli.commands import Command, CommandContext
from henchman.extensions.base import Extension
from henchman.extensions.manager import ExtensionManager
from henchman.tools.base import Tool, ToolKind, ToolResult


class MockTool(Tool):
    """A mock tool for testing."""

    def __init__(self, name: str = "mock_tool") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Mock tool: {self._name}"

    @property
    def parameters(self) -> dict[str, object]:
        return {"type": "object", "properties": {}}

    @property
    def kind(self) -> ToolKind:
        return ToolKind.READ

    async def execute(self, **params: object) -> ToolResult:
        return ToolResult(content="mock")


class MockCommand(Command):
    """A mock command for testing."""

    def __init__(self, name: str = "mock") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Mock command: {self._name}"

    @property
    def usage(self) -> str:
        return f"/{self._name}"

    async def execute(self, ctx: CommandContext) -> None:
        pass


class TestExtensionImpl(Extension):
    """Test extension implementation."""

    @property
    def name(self) -> str:
        return "test_ext"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Test extension"

    def get_tools(self) -> list[Tool]:
        return [MockTool("ext_tool")]

    def get_commands(self) -> list[Command]:
        return [MockCommand("ext_cmd")]

    def get_context(self) -> str:
        return "Extension context"


class AnotherExtension(Extension):
    """Another test extension."""

    @property
    def name(self) -> str:
        return "another_ext"

    @property
    def version(self) -> str:
        return "2.0.0"

    @property
    def description(self) -> str:
        return "Another extension"

    def get_tools(self) -> list[Tool]:
        return [MockTool("another_tool")]


class TestExtensionManager:
    """Tests for ExtensionManager."""

    def test_init_empty(self) -> None:
        """Test manager initializes empty."""
        manager = ExtensionManager()
        assert manager.list_extensions() == []

    def test_register_extension(self) -> None:
        """Test registering an extension."""
        manager = ExtensionManager()
        ext = TestExtensionImpl()
        manager.register(ext)
        assert "test_ext" in manager.list_extensions()

    def test_get_extension(self) -> None:
        """Test getting an extension by name."""
        manager = ExtensionManager()
        ext = TestExtensionImpl()
        manager.register(ext)
        assert manager.get("test_ext") is ext
        assert manager.get("nonexistent") is None

    def test_register_multiple_extensions(self) -> None:
        """Test registering multiple extensions."""
        manager = ExtensionManager()
        manager.register(TestExtensionImpl())
        manager.register(AnotherExtension())
        names = manager.list_extensions()
        assert "test_ext" in names
        assert "another_ext" in names

    def test_duplicate_registration_replaces(self) -> None:
        """Test duplicate registration replaces existing."""
        manager = ExtensionManager()
        ext1 = TestExtensionImpl()
        ext2 = TestExtensionImpl()
        manager.register(ext1)
        manager.register(ext2)
        assert manager.get("test_ext") is ext2

    def test_get_all_tools(self) -> None:
        """Test getting all tools from extensions."""
        manager = ExtensionManager()
        manager.register(TestExtensionImpl())
        manager.register(AnotherExtension())
        tools = manager.get_all_tools()
        tool_names = [t.name for t in tools]
        assert "ext_tool" in tool_names
        assert "another_tool" in tool_names

    def test_get_all_commands(self) -> None:
        """Test getting all commands from extensions."""
        manager = ExtensionManager()
        manager.register(TestExtensionImpl())
        commands = manager.get_all_commands()
        cmd_names = [c.name for c in commands]
        assert "ext_cmd" in cmd_names

    def test_get_combined_context(self) -> None:
        """Test getting combined context from extensions."""
        manager = ExtensionManager()
        manager.register(TestExtensionImpl())
        context = manager.get_combined_context()
        assert "Extension context" in context

    def test_unregister_extension(self) -> None:
        """Test unregistering an extension."""
        manager = ExtensionManager()
        manager.register(TestExtensionImpl())
        assert manager.unregister("test_ext") is True
        assert manager.get("test_ext") is None
        assert manager.unregister("nonexistent") is False


class TestEntryPointDiscovery:
    """Tests for entry point extension discovery."""

    def test_discover_entry_points_empty(self) -> None:
        """Test discovery with no entry points."""
        manager = ExtensionManager()
        with patch("henchman.extensions.manager.entry_points") as mock_eps:
            mock_eps.return_value = []
            manager.discover_entry_points()
        assert manager.list_extensions() == []

    def test_discover_entry_points_loads_extension(self) -> None:
        """Test discovery loads extensions from entry points."""
        manager = ExtensionManager()

        # Create a mock entry point
        mock_ep = MagicMock()
        mock_ep.name = "test_entry"
        mock_ep.load.return_value = TestExtensionImpl

        with patch("henchman.extensions.manager.entry_points") as mock_eps:
            mock_eps.return_value = [mock_ep]
            manager.discover_entry_points()

        assert "test_ext" in manager.list_extensions()

    def test_discover_entry_points_handles_error(self) -> None:
        """Test discovery handles loading errors gracefully."""
        manager = ExtensionManager()

        mock_ep = MagicMock()
        mock_ep.name = "broken"
        mock_ep.load.side_effect = Exception("Load failed")

        with patch("henchman.extensions.manager.entry_points") as mock_eps:
            mock_eps.return_value = [mock_ep]
            # Should not raise
            manager.discover_entry_points()

        assert manager.list_extensions() == []

    def test_discover_entry_points_python_310_compat(self) -> None:
        """Test discovery handles Python < 3.10 API."""
        manager = ExtensionManager()

        mock_ep = MagicMock()
        mock_ep.name = "compat_entry"
        mock_ep.load.return_value = TestExtensionImpl

        # Mock for Python < 3.10 fallback path
        mock_dict = MagicMock()
        mock_dict.get.return_value = [mock_ep]

        def side_effect(**kwargs: object) -> MagicMock:
            if "group" in kwargs:
                raise TypeError("unexpected keyword argument 'group'")
            return mock_dict

        with patch("henchman.extensions.manager.entry_points", side_effect=side_effect):
            manager.discover_entry_points()

        assert "test_ext" in manager.list_extensions()

    def test_discover_entry_points_not_subclass(self) -> None:
        """Test discovery handles entry point that's not an Extension subclass."""
        manager = ExtensionManager()

        mock_ep = MagicMock()
        mock_ep.name = "not_extension"
        mock_ep.load.return_value = "not a class"

        with patch("henchman.extensions.manager.entry_points") as mock_eps:
            mock_eps.return_value = [mock_ep]
            manager.discover_entry_points()

        assert manager.list_extensions() == []


class TestDirectoryDiscovery:
    """Tests for directory-based extension discovery."""

    def test_discover_directory_no_dir(self, tmp_path: Path) -> None:
        """Test discovery with non-existent directory."""
        manager = ExtensionManager()
        manager.discover_directory(tmp_path / "nonexistent")
        assert manager.list_extensions() == []

    def test_discover_directory_empty(self, tmp_path: Path) -> None:
        """Test discovery with empty directory."""
        ext_dir = tmp_path / "extensions"
        ext_dir.mkdir()
        manager = ExtensionManager()
        manager.discover_directory(ext_dir)
        assert manager.list_extensions() == []

    def test_discover_directory_loads_extension(self, tmp_path: Path) -> None:
        """Test discovery loads extension from directory."""
        ext_dir = tmp_path / "extensions"
        ext_dir.mkdir()

        # Create an extension directory
        my_ext = ext_dir / "my_ext"
        my_ext.mkdir()

        # Create extension.py
        (my_ext / "extension.py").write_text("""
from henchman.extensions.base import Extension

class MyExtension(Extension):
    @property
    def name(self) -> str:
        return "my_ext"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "My extension"
""")

        manager = ExtensionManager()
        manager.discover_directory(ext_dir)
        assert "my_ext" in manager.list_extensions()

    def test_discover_directory_handles_invalid_extension(self, tmp_path: Path) -> None:
        """Test discovery handles invalid extension.py gracefully."""
        ext_dir = tmp_path / "extensions"
        ext_dir.mkdir()

        bad_ext = ext_dir / "bad_ext"
        bad_ext.mkdir()
        (bad_ext / "extension.py").write_text("syntax error!!!")

        manager = ExtensionManager()
        # Should not raise
        manager.discover_directory(ext_dir)
        assert manager.list_extensions() == []

    def test_discover_directory_handles_missing_class(self, tmp_path: Path) -> None:
        """Test discovery handles extension.py without Extension class."""
        ext_dir = tmp_path / "extensions"
        ext_dir.mkdir()

        no_class = ext_dir / "no_class"
        no_class.mkdir()
        (no_class / "extension.py").write_text("# No extension class here")

        manager = ExtensionManager()
        manager.discover_directory(ext_dir)
        assert manager.list_extensions() == []

    def test_discover_directory_skips_files(self, tmp_path: Path) -> None:
        """Test discovery skips regular files in extension directory."""
        ext_dir = tmp_path / "extensions"
        ext_dir.mkdir()

        # Create a regular file (not a directory)
        (ext_dir / "not_a_dir.txt").write_text("hello")

        manager = ExtensionManager()
        manager.discover_directory(ext_dir)
        assert manager.list_extensions() == []

    def test_discover_directory_skips_dirs_without_extension_py(
        self, tmp_path: Path
    ) -> None:
        """Test discovery skips directories without extension.py."""
        ext_dir = tmp_path / "extensions"
        ext_dir.mkdir()

        # Create a directory without extension.py
        (ext_dir / "no_ext_file").mkdir()

        manager = ExtensionManager()
        manager.discover_directory(ext_dir)
        assert manager.list_extensions() == []

    def test_discover_directory_handles_instantiation_failure(
        self, tmp_path: Path
    ) -> None:
        """Test discovery handles extension that fails to instantiate."""
        ext_dir = tmp_path / "extensions"
        ext_dir.mkdir()

        fail_ext = ext_dir / "fail_ext"
        fail_ext.mkdir()
        (fail_ext / "extension.py").write_text("""
from henchman.extensions.base import Extension

class FailExtension(Extension):
    def __init__(self):
        raise ValueError("Cannot instantiate")

    @property
    def name(self) -> str:
        return "fail_ext"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Fails to init"
""")

        manager = ExtensionManager()
        manager.discover_directory(ext_dir)
        assert manager.list_extensions() == []

    def test_discover_directory_handles_load_exception(self, tmp_path: Path) -> None:
        """Test discovery handles exception from _load_extension_from_file."""
        manager = ExtensionManager()

        ext_dir = tmp_path / "extensions"
        ext_dir.mkdir()
        fail_dir = ext_dir / "fail"
        fail_dir.mkdir()
        (fail_dir / "extension.py").write_text("pass")

        with patch.object(
            manager, "_load_extension_from_file", side_effect=RuntimeError("Boom!")
        ):
            manager.discover_directory(ext_dir)

        assert manager.list_extensions() == []

    def test_load_extension_from_file_spec_none(self, tmp_path: Path) -> None:
        """Test _load_extension_from_file handles None spec."""
        manager = ExtensionManager()
        ext_file = tmp_path / "extension.py"
        ext_file.write_text("pass")

        with patch("henchman.extensions.manager.importlib.util.spec_from_file_location") as m:
            m.return_value = None
            manager._load_extension_from_file(ext_file, "test")

        assert manager.list_extensions() == []

        assert manager.list_extensions() == []
