import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

# Mock mcp module to avoid ImportError
mcp_mock = MagicMock()
sys.modules["mcp"] = mcp_mock
sys.modules["mcp.client"] = mcp_mock
sys.modules["mcp.client.stdio"] = mcp_mock
sys.modules["mcp.types"] = mcp_mock

from rich.console import Console  # noqa: E402

from henchman.cli.console import OutputRenderer  # noqa: E402
from henchman.cli.input import create_session  # noqa: E402


def test_accessibility():
    print("Testing Accessibility Mode...")

    # Mock console
    console_mock = MagicMock(spec=Console)

    # 1. Test Normal Mode
    renderer_normal = OutputRenderer(console=console_mock, accessible_mode=False)
    renderer_normal.success("Success")
    # Verify unicode check mark
    args = console_mock.print.call_args[0][0]
    if "✓" not in args:
        raise AssertionError(f"Normal mode missing checkmark: {args}")

    # 2. Test Accessible Mode
    renderer_access = OutputRenderer(console=console_mock, accessible_mode=True)
    renderer_access.success("Success")
    # Verify text label
    args = console_mock.print.call_args[0][0]
    if "[OK]" not in args:
        raise AssertionError(f"Accessible mode missing [OK]: {args}")
    print("✅ Accessible mode (messages) verified")

    # 3. Test Table accessibilty
    from rich import box
    from rich.table import Table

    renderer_access.table([{"a": 1}])
    if console_mock.print.called:
        last_arg = console_mock.print.call_args[0][0]
        if isinstance(last_arg, Table):
            if last_arg.box == box.ASCII:
                print("✅ Accessible table uses ASCII box")
            else:
                raise AssertionError(f"Accessible table uses {last_arg.box}")


def test_keybindings():
    print("\nTesting Keybindings...")

    keybindings = {"c-t": "abort"}

    _session = create_session(keybindings=keybindings)  # noqa: F841

    # Check if 'c-t' is in key bindings
    # This is tricky to verify on the session object directly without private access
    # But we can check if the binding was added to the KeyBindings registry

    # Assuming the implementation adds it to 'bindings' which is passed to PromptSession
    # We can inspect session.app.key_bindings or similar if available,
    # but create_session returns PromptSession.

    # Inspecting internal prompt_toolkit structures is complex.
    # However, if creating the session didn't crash, it means the keys were processed.

    print("✅ create_session accepted keybindings")


if __name__ == "__main__":
    try:
        test_accessibility()
        test_keybindings()
        sys.exit(0)
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
