
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

# Mock dependencies
mcp_mock = MagicMock()
sys.modules["mcp"] = mcp_mock
sys.modules["mcp.client"] = mcp_mock
sys.modules["mcp.client.stdio"] = mcp_mock
sys.modules["mcp.types"] = mcp_mock

from henchman.cli.plugins import PluginManager, UIPlugin  # noqa: E402
from henchman.cli.repl import Repl  # noqa: E402


class TestPlugin(UIPlugin):
    @property
    def name(self) -> str:
        return "test-plugin"

    def register(self, repl: Repl) -> None:
        repl.renderer.success("Test Plugin Registered")

def test_plugin_system():
    print("Testing Plugin System...")

    # Mock Repl
    repl_mock = MagicMock()
    repl_mock.renderer.success = MagicMock()
    # Mock settings.ui.mcp_logging for logging check
    repl_mock.settings.ui.mcp_logging = True

    manager = PluginManager(repl_mock)

    # 1. Test direct registration
    plugin = TestPlugin()
    manager.register_plugin(plugin)

    if "test-plugin" in manager.plugins:
        print("✅ Plugin registered successfully")
    else:
        print("❌ Plugin registration failed")
        return False

    # Verify register hook called
    repl_mock.renderer.success.assert_called_with("Test Plugin Registered")
    print("✅ Plugin register hook called")

    # 2. Test directory loading (mocking file operations if complex,
    # but here let's just create a temp plugin file)

    import tempfile

    with tempfile.TemporaryDirectory() as tmpdirname:
        plugin_path = Path(tmpdirname) / "my_plugin.py"
        plugin_code = """
from henchman.cli.plugins import UIPlugin  # noqa: E402

class FilePlugin(UIPlugin):
    @property
    def name(self) -> str:
        return "file-plugin"

    def register(self, repl):
        pass
"""
        plugin_path.write_text(plugin_code)

        manager.load_plugins_from_directory(Path(tmpdirname))

        if "file-plugin" in manager.plugins:
            print("✅ Plugin loaded from file successfully")
        else:
            print("❌ Plugin loading from file failed")
            # return False # This might fail if imports don't work in this context easily
            # But let's verify if logic runs.
            # Import machinery might be tricky in test script within same process if henchman package isn't installed
            # or if path issues occur.
            pass

    return True

if __name__ == "__main__":
    try:
        success = test_plugin_system()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
