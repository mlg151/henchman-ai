
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
from rich.syntax import Syntax  # noqa: E402
from rich.table import Table  # noqa: E402
from rich.tree import Tree  # noqa: E402

from henchman.cli.console import OutputRenderer  # noqa: E402


def test_visualization():
    print("Testing Output Visualization...")

    # Mock console
    console_mock = MagicMock(spec=Console)
    renderer = OutputRenderer(console=console_mock)

    # 1. Test Table Rendering
    print("Testing table rendering...")
    data = [
        {"name": "Alice", "role": "Engineer"},
        {"name": "Bob", "role": "Designer"}
    ]
    renderer.table(data, title="Team")

    # Verify console.print was called with a Table
    # print_calls = console_mock.print.call_args_list
    # table_call = next((call for call in print_calls if isinstance(call[0][0], Table)), None)
    # The first arg of the last call should be the table
    if console_mock.print.called:
        last_arg = console_mock.print.call_args[0][0]
        if isinstance(last_arg, Table):
            print("✅ Table rendered successfully")
            if last_arg.title == "Team":
                print("✅ Table title correct")
            else:
                 print(f"❌ Table title mismatch: {last_arg.title}")
                 return False

            # Check columns (might need internal access or check row count)
            if len(last_arg.columns) == 2:
                print("✅ Table columns correct")
            else:
                print(f"❌ Table columns mismatch: {len(last_arg.columns)}")
                return False
        else:
            print(f"❌ Expected Table, got {type(last_arg)}")
            return False
    else:
        print("❌ console.print not called for table")
        return False

    # 2. Test Tree Rendering
    print("\nTesting tree rendering...")
    tree_data = [
        ("src/main.py", "File"),
        ("src/utils/helper.py", "File"),
        ("tests/test_main.py", "Test")
    ]
    renderer.tree("Project", tree_data)

    if console_mock.print.called:
        last_arg = console_mock.print.call_args[0][0]
        if isinstance(last_arg, Tree):
            print("✅ Tree rendered successfully")
            if "Project" in str(last_arg.label):
                print("✅ Tree root label correct")
            else:
                print(f"❌ Tree root label mismatch: {last_arg.label}")
                return False
        else:
            print(f"❌ Expected Tree, got {type(last_arg)}")
            return False
    else:
        print("❌ console.print not called for tree")
        return False

    # 3. Test Diff Rendering
    print("\nTesting diff rendering...")
    old = "def foo():\n    return 1\n"
    new = "def foo():\n    return 2\n"
    renderer.diff(old, new, filename="test.py")

    if console_mock.print.called:
        last_arg = console_mock.print.call_args[0][0]
        if isinstance(last_arg, Syntax):
            print("✅ Diff rendered successfully (Syntax)")
            if last_arg.lexer.name.lower() == "diff":
                print("✅ Diff lexer correct")
            else:
                print(f"❌ Diff lexer mismatch: {last_arg.lexer.name}")
                return False
        else:
            print(f"❌ Expected Syntax, got {type(last_arg)}")
            return False
    else:
        print("❌ console.print not called for diff")
        return False

    return True

if __name__ == "__main__":
    try:
        success = test_visualization()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
