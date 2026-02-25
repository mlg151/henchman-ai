#!/usr/bin/env python3
"""Test if Textual Input works in this terminal."""

import os
import sys

# Check terminal capabilities
print("=== Terminal Capabilities Check ===")
print(f"TERM: {os.environ.get('TERM', 'not set')}")
print(f"COLORTERM: {os.environ.get('COLORTERM', 'not set')}")
print(f"TERM_PROGRAM: {os.environ.get('TERM_PROGRAM', 'not set')}")

# Check if we're in a proper terminal
if sys.stdout.isatty():
    print("✓ stdout is a TTY")
else:
    print("✗ stdout is NOT a TTY (might be pipe/redirect)")

# Simple test: can we write ANSI codes?
print("\n=== ANSI Escape Code Test ===")
print("\033[32mGreen text\033[0m - should be green")
print("\033[1mBold text\033[0m - should be bold")
print("\033[7mInverse text\033[0m - should be inverse")

print("\n=== Textual Input Test ===")
print("If you can see the colored text above, terminal supports ANSI.")
print("If Textual Input doesn't show typed text, it's likely a:")
print("1. Textual bug with your terminal")
print("2. Focus issue")
print("3. Terminal emulator compatibility issue")

print("\n=== Recommendation ===")
print("Try running in different terminal:")
print("- Gnome Terminal, Konsole, iTerm2, Alacritty")
print("Avoid: Windows Terminal/Cmd, VS Code integrated terminal")
