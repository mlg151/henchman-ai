import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

# Mock mcp module to avoid ImportError
mcp_mock = MagicMock()
sys.modules["mcp"] = mcp_mock
sys.modules["mcp.client"] = mcp_mock
sys.modules["mcp.client.stdio"] = mcp_mock
sys.modules["mcp.types"] = mcp_mock

sys.modules["mcp.types"] = mcp_mock

from henchman.cli.ui_renderer import ProgressManager  # noqa: E402


def test_progress_manager():
    print("Testing ProgressManager...")

    # Mock rich.progress where it is used
    with patch("henchman.cli.ui_renderer.Progress") as progress_class_mock:
        progress_mock = MagicMock()
        progress_class_mock.return_value = progress_mock

        # Mock console to avoid actual output
        console = MagicMock()
        console.get_time.return_value = time.time()
        console.size = (80, 24)
        console.is_terminal = False
        console.encoding = "utf-8"

        pm = ProgressManager(console)

        # Test starting a task
        print("Starting task...")
        _progress = pm.start_task("task1", "Downloading", total=100)

        if "task1" not in pm.tasks:
            print("❌ Task not added to manager")
            return False

        # Check if progress was started
        if not progress_mock.start.called:
            print("❌ Progress.start() not called")
            return False

        # Test updating a task
        print("Updating task...")
        pm.update_task("task1", advance=50)

        # Verify update was called on the correct Progress instance
        if not progress_mock.update.called:
             print("❌ Progress.update() not called")
             return False

        # Test completing a task
        print("Completing task...")
        pm.complete_task("task1")

        if "task1" in pm.tasks:
            print("❌ Task not removed after completion")
            return False

        if not progress_mock.stop.called:
            print("❌ Progress.stop() not called")
            return False

        print("✅ ProgressManager basic operations working")
        return True

if __name__ == "__main__":
    try:
        success = test_progress_manager()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Exception: {e}")
        sys.exit(1)
