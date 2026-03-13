#!/usr/bin/env python3
"""Test the refactored shell tool."""

import asyncio
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .shell_refactor import ShellTool


async def test_refactored_tool():
    """Test the refactored shell tool."""
    tool = ShellTool()

    print("Testing refactored ShellTool...")

    # Test 1: Simple command
    result = await tool.execute(command="echo hello")
    print(f"1. Simple command test: {'PASS' if result.success and 'hello' in result.content else 'FAIL'}")
    if not result.success:
        print(f"   Error: {result.error}")

    # Test 2: Error handling
    result = await tool.execute(command="exit 1")
    print(f"2. Error code test: {'PASS' if not result.success else 'FAIL'}")

    # Test 3: Environment variable
    result = await tool.execute(command="echo $HENCHMAN_CLI")
    print(f"3. Env variable test: {'PASS' if result.success and '1' in result.content else 'FAIL'}")

    # Test 4: Working directory
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        result = await tool.execute(command="pwd", cwd=tmpdir)
        print(f"4. Working directory test: {'PASS' if result.success and tmpdir in result.content else 'FAIL'}")

    # Test 5: Sudo detection
    print(f"5. Sudo detection test: {'PASS' if tool._is_sudo_command('sudo ls') else 'FAIL'}")
    print(f"6. Non-sudo detection test: {'PASS' if not tool._is_sudo_command('ls') else 'FAIL'}")

    print("\nAll tests completed!")


if __name__ == "__main__":
    asyncio.run(test_refactored_tool())
