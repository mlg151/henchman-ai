"""Chaos script for Bug #9 & #10: Path traversal and unbounded file reading.

This script demonstrates the security vulnerabilities in expand_at_references.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from henchman.cli.input import expand_at_references


async def test_path_traversal() -> None:
    """Test path traversal vulnerability."""
    print("=== Testing Path Traversal Vulnerability ===")

    # Create a test file in temp directory
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("SECRET_DATA: Should not be accessible via path traversal")
        temp_file = Path(f.name)

    try:
        # Try to access file with path traversal
        test_input = f"Check this file @../../../{temp_file}"
        print(f"Input: {test_input}")

        result = await expand_at_references(test_input)

        if "SECRET_DATA" in result:
            print("❌ VULNERABLE: Path traversal allowed!")
            print(f"Result: {result[:200]}...")
        else:
            print("✅ FIXED: Path traversal blocked")
            print(f"Result: {result[:200]}...")
    finally:
        temp_file.unlink()


async def test_large_file_reading() -> None:
    """Test unbounded file reading vulnerability."""
    print("\n=== Testing Unbounded File Reading ===")

    # Create a large file (11 MB, exceeding the 10 MB limit)
    large_file = Path("/tmp/test_large_file.txt")
    try:
        # Write 11 MB of data
        with open(large_file, 'w') as f:
            # Write 11,000,000 bytes (11 MB)
            for _ in range(1100):
                f.write("A" * 10000)  # 10KB per line

        print(f"Created large file: {large_file.stat().st_size} bytes")

        test_input = f"Check large file @{large_file}"
        print(f"Input: {test_input}")

        result = await expand_at_references(test_input)

        if "File too large" in result:
            print("✅ FIXED: File size limit enforced")
        else:
            print("❌ VULNERABLE: Large file read without limit")
            print(f"Result length: {len(result)} characters")
    finally:
        if large_file.exists():
            large_file.unlink()


async def test_safe_file_reading() -> None:
    """Test that safe file reading still works."""
    print("\n=== Testing Safe File Reading ===")

    # Create a small safe file
    safe_file = Path("/tmp/test_safe_file.txt")
    try:
        with open(safe_file, 'w') as f:
            f.write("This is a safe test file.")

        test_input = f"Check safe file @{safe_file}"
        print(f"Input: {test_input}")

        result = await expand_at_references(test_input)

        if "safe test file" in result:
            print("✅ Safe file reading works correctly")
        else:
            print("❌ Safe file reading broken")
    finally:
        if safe_file.exists():
            safe_file.unlink()


async def main() -> None:
    """Run all chaos tests."""
    print("Running Chaos Scripts for Bugs #9 & #10")
    print("=" * 50)

    await test_path_traversal()
    await test_large_file_reading()
    await test_safe_file_reading()

    print("\n" + "=" * 50)
    print("Chaos tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
