"""Verify that the asyncio.Lock bug is actually fixed."""

import asyncio
import threading

def test_asyncio_lock_usage():
    """Check that code doesn't use 'with' on asyncio.Lock."""
    import inspect
    import henchman.cli.textual_mixins as module
    
    # Check _init_confirm_state
    init_source = inspect.getsource(module._InitMixin._init_confirm_state)
    print("=== _init_confirm_state ===")
    print(init_source)
    
    if "asyncio.Lock" in init_source:
        print("✓ Uses asyncio.Lock")
    elif "threading.Lock" in init_source:
        print("✗ Still uses threading.Lock (BUG)")
    
    # Check _textual_confirm for async with
    confirm_source = inspect.getsource(module._InitMixin._textual_confirm)
    print("\n=== _textual_confirm lock usage ===")
    
    lines = confirm_source.split('\n')
    for i, line in enumerate(lines):
        if 'self._confirm_lock' in line:
            print(f"Line ~{i}: {line.strip()}")
    
    # Count async with vs with
    async_with_count = confirm_source.count('async with self._confirm_lock')
    with_count = confirm_source.count('with self._confirm_lock') - async_with_count
    
    print(f"\nasync with count: {async_with_count}")
    print(f"with count (should be 0): {with_count}")
    
    if with_count > 0:
        print("✗ Still uses 'with' on asyncio.Lock (BUG)")
    else:
        print("✓ All uses are 'async with'")
    
    # Check _cleanup_confirm_futures
    cleanup_source = inspect.getsource(module._InitMixin._cleanup_confirm_futures)
    print("\n=== _cleanup_confirm_futures ===")
    
    if 'with self._confirm_lock' in cleanup_source:
        print("✗ Uses 'with' on asyncio.Lock in sync context (BUG)")
    else:
        print("✓ Doesn't use lock in sync context (correct)")
    
    # Check for comment about accepting races
    if 'accept potential races' in cleanup_source or 'shutdown cleanup' in cleanup_source:
        print("✓ Has comment about accepting races during shutdown")
    
    return with_count == 0 and 'with self._confirm_lock' not in cleanup_source

if __name__ == "__main__":
    try:
        success = test_asyncio_lock_usage()
        if success:
            print("\n✅ All checks passed! The bug appears to be fixed.")
        else:
            print("\n❌ Some checks failed. Bug may still exist.")
    except Exception as e:
        print(f"\n❌ Error running test: {e}")
        import traceback
        traceback.print_exc()