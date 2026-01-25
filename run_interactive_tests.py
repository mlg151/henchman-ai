#!/usr/bin/env python3
"""
Interactive Session Functional Test Runner

This script runs comprehensive functional tests for interactive sessions
to shake out integration bugs.

Usage:
    python run_interactive_tests.py     # Run all tests
    python run_interactive_tests.py --quick  # Run quick tests only
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint


def run_comprehensive_test():
    """Run the comprehensive interactive session test."""
    console = Console()
    
    rprint(Panel.fit("[bold cyan]Running Comprehensive Interactive Session Test[/]", border_style="cyan"))
    
    try:
        # Import and run the comprehensive test
        from tests.ui_integration.test_runnable_interactive_session import run_all_tests
        run_all_tests()
        return True
    except Exception as e:
        console.print(f"[bold red]Error in comprehensive test: {e}[/]")
        import traceback
        console.print(traceback.format_exc())
        return False


def run_individual_tests():
    """Run individual component tests."""
    console = Console()
    
    rprint(Panel.fit("[bold cyan]Running Individual Component Tests[/]", border_style="cyan"))
    
    test_results = []
    
    # Test 1: Basic session
    try:
        from tests.ui_integration.test_runnable_interactive_session import test_basic_interactive_session
        asyncio.run(test_basic_interactive_session())
        test_results.append(("Basic Interactive Session", "✓ PASSED"))
    except Exception as e:
        test_results.append(("Basic Interactive Session", f"✗ FAILED: {e}"))
    
    # Test 2: Tool calls
    try:
        from tests.ui_integration.test_runnable_interactive_session import test_tool_calls_in_session
        asyncio.run(test_tool_calls_in_session())
        test_results.append(("Tool Calls in Session", "✓ PASSED"))
    except Exception as e:
        test_results.append(("Tool Calls in Session", f"✗ FAILED: {e}"))
    
    # Test 3: Plan mode
    try:
        from tests.ui_integration.test_runnable_interactive_session import test_plan_mode_integration
        asyncio.run(test_plan_mode_integration())
        test_results.append(("Plan Mode Integration", "✓ PASSED"))
    except Exception as e:
        test_results.append(("Plan Mode Integration", f"✗ FAILED: {e}"))
    
    # Test 4: Skills
    try:
        from tests.ui_integration.test_runnable_interactive_session import test_skills_integration
        asyncio.run(test_skills_integration())
        test_results.append(("Skills Integration", "✓ PASSED"))
    except Exception as e:
        test_results.append(("Skills Integration", f"✗ FAILED: {e}"))
    
    # Display results
    table = Table(title="Component Test Results")
    table.add_column("Test", style="cyan")
    table.add_column("Result", style="green")
    
    for test_name, result in test_results:
        table.add_row(test_name, result)
    
    console.print(table)
    
    # Count passed/failed
    passed = sum(1 for _, result in test_results if "PASSED" in result)
    failed = len(test_results) - passed
    
    return passed, failed


def run_pytest_tests():
    """Run tests using pytest."""
    import subprocess
    
    console = Console()
    
    rprint(Panel.fit("[bold cyan]Running Pytest Tests[/]", border_style="cyan"))
    
    test_files = [
        "tests/ui_integration/test_runnable_interactive_session.py",
        "tests/ui_integration/test_comprehensive_interactive_session.py",
        "tests/ui_integration/test_repl_e2e.py",
        "tests/ui_integration/test_tool_integration.py",
        "tests/ui_integration/test_slash_commands.py",
        "tests/ui_integration/test_plan_mode.py",
        "tests/ui_integration/test_skills.py",
    ]
    
    # Check which files exist
    existing_files = []
    for test_file in test_files:
        if Path(test_file).exists():
            existing_files.append(test_file)
        else:
            console.print(f"[yellow]Note: {test_file} not found[/]")
    
    if not existing_files:
        console.print("[red]No test files found![/]")
        return 0, 0
    
    # Run pytest
    cmd = ["python", "-m", "pytest", "-v"] + existing_files
    console.print(f"[dim]Running: {' '.join(cmd)}[/]")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Parse output
        console.print(result.stdout)
        if result.stderr:
            console.print(f"[yellow]Stderr: {result.stderr}[/]")
        
        # Try to parse pytest summary
        lines = result.stdout.split('\n')
        passed = 0
        failed = 0
        
        for line in lines:
            if "passed" in line and "failed" in line:
                # Parse something like: "5 passed, 2 failed in 0.12s"
                parts = line.split()
                for part in parts:
                    if part.endswith("passed"):
                        passed = int(part.split()[0]) if part[0].isdigit() else 0
                    elif part.endswith("failed"):
                        failed = int(part.split()[0]) if part[0].isdigit() else 0
        
        return passed, failed
        
    except Exception as e:
        console.print(f"[red]Error running pytest: {e}[/]")
        return 0, 0


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Run interactive session functional tests")
    parser.add_argument("--quick", action="store_true", help="Run quick tests only")
    parser.add_argument("--pytest", action="store_true", help="Run tests using pytest")
    parser.add_argument("--components", action="store_true", help="Run individual component tests")
    args = parser.parse_args()
    
    console = Console()
    
    rprint(Panel.fit("[bold green]Interactive Session Functional Test Runner[/]", border_style="green"))
    
    console.print("[dim]This test suite validates:[/]")
    console.print("  • Multiple message exchanges between user and henchman")
    console.print("  • Several tool calls (file operations, shell commands)")
    console.print("  • Skills usage (learning and executing skills)")
    console.print("  • Planning session that is started and ended")
    console.print("")
    
    total_passed = 0
    total_failed = 0
    
    if args.pytest:
        # Run pytest tests
        passed, failed = run_pytest_tests()
        total_passed += passed
        total_failed += failed
    
    elif args.components:
        # Run individual component tests
        passed, failed = run_individual_tests()
        total_passed += passed
        total_failed += failed
    
    elif args.quick:
        # Run quick test only
        console.print("[yellow]Running quick test...[/]")
        success = run_comprehensive_test()
        if success:
            total_passed += 1
        else:
            total_failed += 1
    
    else:
        # Run everything
        console.print("[bold]Running full test suite...[/]")
        console.print("")
        
        # 1. Run comprehensive test
        success = run_comprehensive_test()
        if success:
            total_passed += 1
        else:
            total_failed += 1
        
        console.print("")
        
        # 2. Run individual component tests
        passed, failed = run_individual_tests()
        total_passed += passed
        total_failed += failed
        
        console.print("")
        
        # 3. Run pytest tests
        passed, failed = run_pytest_tests()
        total_passed += passed
        total_failed += failed
    
    # Summary
    console.print("")
    rprint(Panel.fit(f"[bold]Test Summary: {total_passed} passed, {total_failed} failed[/]", 
                     border_style="green" if total_failed == 0 else "red"))
    
    if total_failed == 0:
        console.print("[bold green]✓ All tests passed! Interactive session workflow is functional.[/]")
        console.print("[dim]The system supports:[/]")
        console.print("  • Multi-turn conversations with context maintenance")
        console.print("  • Tool execution through the UI")
        console.print("  • Skills learning and execution")
        console.print("  • Planning mode toggling")
        console.print("  • Session persistence throughout workflow")
        return 0
    else:
        console.print(f"[bold red]✗ {total_failed} test(s) failed. Integration issues detected.[/]")
        console.print("[yellow]Check the test output above for details.[/]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
