#!/usr/bin/env python3
"""Test Henchman CLI directly."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Clear any cached modules
if 'henchman' in sys.modules:
    del sys.modules['henchman']
if 'henchman.cli' in sys.modules:
    del sys.modules['henchman.cli']
if 'henchman.cli.app' in sys.modules:
    del sys.modules['henchman.cli.app']

from henchman.cli.app import cli

if __name__ == '__main__':
    # Test xyztest command
    print("Testing xyztest command...")
    sys.argv = ['henchman', 'xyztest', '--help']
    try:
        cli()
    except SystemExit:
        pass
    
    print("\n" + "="*50 + "\n")
    
    # Test serve command
    print("Testing serve command...")
    sys.argv = ['henchman', 'serve', '--help']
    try:
        cli()
    except SystemExit:
        pass