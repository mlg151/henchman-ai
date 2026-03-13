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

from rich import box  # noqa: E402
from rich.console import Console  # noqa: E402

from henchman.cli.console import OutputRenderer  # noqa: E402


def test_layout_settings():
    print("Testing Layout Settings...")

    # Mock settings object
    class MockLayoutSettings:
        compact_tables = True

    layout_settings = MockLayoutSettings()

    console_mock = MagicMock(spec=Console)

    # 1. Test OutputRenderer with compact_tables=True
    renderer = OutputRenderer(console=console_mock, layout_settings=layout_settings)

    # Render a table
    renderer.table([{"a": 1}])

    # Check if box.MINIMAL was used
    # We need to inspect the 'box' attribute of the Table object passed to console.print
    if console_mock.print.called:
        last_arg = console_mock.print.call_args[0][0]
        from rich.table import Table

        if isinstance(last_arg, Table):
            if last_arg.box == box.MINIMAL:
                print("✅ Compact table setting applied (box.MINIMAL used)")
            else:
                print(f"❌ Compact table setting failed. Box used: {last_arg.box}")
                return False
        else:
            print("❌ print called but not with Table")
            return False
    else:
        print("❌ console.print not called")
        return False

    return True


if __name__ == "__main__":
    try:
        success = test_layout_settings()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
