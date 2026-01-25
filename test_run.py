#!/usr/bin/env python3
"""
Run the interactive session test.
"""
import asyncio
import sys
sys.path.insert(0, '.')

from tests.ui_integration.test_runnable_interactive_session import (
    test_basic_interactive_session,
    test_tool_calls_in_session,
    test_plan_mode_integration,
    test_complete_workflow
)

async def run_tests():
    print("Running interactive session tests...")
    print("=" * 60)
    
    try:
        await test_basic_interactive_session()
        print("✓ Basic interactive session")
    except Exception as e:
        print(f"✗ Basic interactive session failed: {e}")
        import traceback
        traceback.print_exc()
    
    try:
        await test_tool_calls_in_session()
        print("✓ Tool calls in session")
    except Exception as e:
        print(f"✗ Tool calls in session failed: {e}")
    
    try:
        await test_plan_mode_integration()
        print("✓ Plan mode integration")
    except Exception as e:
        print(f"✗ Plan mode integration failed: {e}")
    
    try:
        await test_complete_workflow()
        print("✓ Complete workflow")
    except Exception as e:
        print(f"✗ Complete workflow failed: {e}")
    
    print("=" * 60)
    print("Test run completed.")

if __name__ == "__main__":
    asyncio.run(run_tests())
