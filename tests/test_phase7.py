import asyncio
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

from henchman.cli.console import AsyncOutputRenderer, OutputRenderer  # noqa: E402
from henchman.tools.builtins.file_read import ReadFileTool  # noqa: E402


async def test_async_renderer():
    print("Testing AsyncOutputRenderer...")

    console_mock = MagicMock()
    renderer = OutputRenderer(console=console_mock)
    async_renderer = AsyncOutputRenderer(renderer)

    # Test async print
    await async_renderer.print("Hello Async")

    # Verify Sync renderer was called
    # Since run_sync is used, it should have been called
    # But run_sync runs in a thread, so we might need to wait or just check if it was called eventually?
    # Actually mock call recording might be tricky across threads if not thread-safe or if timing is off.
    # But for a simple test script, it usually works if we await.

    if console_mock.print.called:
        print("✅ AsyncOutputRenderer.print called underlying renderer")
    else:
        # It's possible mock isn't thread safe or updated yet?
        # But run_sync awaits the thread completion.
        print("❌ AsyncOutputRenderer.print failed to call underlying renderer")
        return False

    return True


async def test_chunked_file_read():
    print("\nTesting Chunked File Read (Async)...")

    tool = ReadFileTool()

    import tempfile

    with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
        # Write 100 lines
        for i in range(100):
            tmp.write(f"Line {i + 1}\n")
        tmp_path = tmp.name

    try:
        # Test 1: Read all
        result = await tool.execute(path=tmp_path)
        if result.success and len(result.content.splitlines()) == 100:
            print("✅ Read all lines successfully")
        else:
            print(f"❌ Read all lines failed: {len(result.content.splitlines())} lines")
            return False

        # Test 2: Read range
        result = await tool.execute(path=tmp_path, start_line=10, end_line=20)
        lines = result.content.splitlines()
        if result.success and len(lines) == 11 and "Line 10" in result.content:
            print("✅ Read Line 10-20 successfully")
        else:
            print(f"❌ Read range failed: Got {len(lines)} lines")
            return False

        # Test 3: Max chars
        result = await tool.execute(path=tmp_path, max_chars=50)  # Should truncate
        if "truncated" in result.content:
            print("✅ Truncation works")
        else:
            print("❌ Truncation failed")
            return False

    finally:
        Path(tmp_path).unlink()

    return True


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        success = loop.run_until_complete(test_async_renderer()) and loop.run_until_complete(
            test_chunked_file_read()
        )
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
