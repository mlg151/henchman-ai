#!/usr/bin/env python3
"""Simple test to verify the lock fix."""

import asyncio
import henchman.cli.textual_mixins as tm

async def test_lock_type():
    """Test that _init_confirm_state creates asyncio.Lock, not threading.Lock."""
    # Create an instance
    mixin = tm._InitMixin.__new__(tm._InitMixin)
    
    # Initialize the state
    mixin._init_confirm_state()
    
    # Check lock type
    lock = mixin._confirm_lock
    print(f"Lock type: {type(lock)}")
    print(f"Module: {lock.__class__.__module__}")
    
    # Check if it's asyncio.Lock
    if isinstance(lock, asyncio.Lock):
        print("✓ Correct: Using asyncio.Lock for async code")
        return True
    else:
        print("✗ Error: Not using asyncio.Lock")
        return False

async def test_async_with_in_source():
    """Test that _textual_confirm uses async with."""
    import inspect
    source = inspect.getsource(tm._InitMixin._textual_confirm)
    
    # Check for async with
    if "async with self._confirm_lock:" in source:
        print("✓ Correct: Using async with for asyncio.Lock")
        return True
    else:
        print("✗ Error: Not using async with")
        return False

async def main():
    print("Testing textual_mixins lock fix...")
    print("-" * 40)
    
    test1_ok = await test_lock_type()
    print()
    
    test2_ok = await test_async_with_in_source()
    print()
    
    if test1_ok and test2_ok:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1

if __name__ == "__main__":
    import sys
    try:
        result = asyncio.run(main())
        sys.exit(result)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)