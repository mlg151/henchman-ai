import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

# Mock mcp module
mcp_mock = MagicMock()
sys.modules["mcp"] = mcp_mock
sys.modules["mcp.client"] = mcp_mock
sys.modules["mcp.client.stdio"] = mcp_mock
sys.modules["mcp.types"] = mcp_mock

from rich.console import Console  # noqa: E402

from henchman.cli.console import OutputRenderer, get_theme  # noqa: E402


def test_style_overrides():
    print("Testing Style Overrides...")

    overrides = {"primary": "magenta", "success": "bright_green"}

    # 1. Test get_theme with overrides
    theme = get_theme("dark", overrides=overrides)
    if theme.primary == "magenta":
        print("✅ Theme primary color overridden correctly")
    else:
        print(f"❌ Theme primary color mismatch: {theme.primary}")
        return False

    if theme.success == "bright_green":
        print("✅ Theme success color overridden correctly")
    else:
        print(f"❌ Theme success color mismatch: {theme.success}")
        return False

    if theme.error == "red":  # default
        print("✅ Theme error color remains default")
    else:
        print(f"❌ Theme error color modified: {theme.error}")
        return False

    # 2. Test OutputRenderer with overrides
    console_mock = MagicMock(spec=Console)
    renderer = OutputRenderer(console=console_mock, style_overrides=overrides)

    if renderer.theme.primary == "magenta":
        print("✅ Renderer applied overrides correctly")
    else:
        print(f"❌ Renderer theme primary mismatch: {renderer.theme.primary}")
        return False

    return True


if __name__ == "__main__":
    try:
        success = test_style_overrides()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
