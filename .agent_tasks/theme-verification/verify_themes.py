#!/usr/bin/env python3
"""Verify that all 8 themes are properly added to ThemeManager."""

import sys

sys.path.insert(0, 'src')

from henchman.cli.console import ThemeManager


def main() -> None:
    """Verify theme requirements."""
    manager = ThemeManager()

    # Test 1: list_themes() returns all 8 themes
    themes = manager.list_themes()
    expected_themes = {
        "dark", "light", "solarized-dark", "solarized-light",
        "monokai", "dracula", "high-contrast-dark", "high-contrast-light"
    }

    print("Test 1: Checking list_themes() returns all 8 themes")
    print(f"  Themes returned: {themes}")
    print(f"  Expected themes: {sorted(expected_themes)}")

    missing = expected_themes - set(themes)
    extra = set(themes) - expected_themes

    if missing:
        print(f"  ❌ Missing themes: {missing}")
        sys.exit(1)
    if extra:
        print(f"  ❌ Extra themes: {extra}")
        sys.exit(1)

    print("  ✅ All 8 themes present")
    print(f"  ✅ Total themes: {len(themes)} (expected: 8)")

    # Test 2: Each theme can be retrieved with get_theme()
    print("\nTest 2: Checking each theme can be retrieved with get_theme()")
    all_good = True
    for theme_name in expected_themes:
        theme = manager.get_theme(theme_name)
        if theme.name != theme_name:
            print(f"  ❌ Theme '{theme_name}' has wrong name: {theme.name}")
            all_good = False
        else:
            print(f"  ✅ Theme '{theme_name}' retrieved successfully")

    # Test 3: Verify default theme behavior
    print("\nTest 3: Checking unknown theme returns default")
    default_theme = manager.get_theme("nonexistent")
    if default_theme.name != "dark":
        print(f"  ❌ Unknown theme should return 'dark', got: {default_theme.name}")
        all_good = False
    else:
        print("  ✅ Unknown theme returns default 'dark' theme")

    if all_good:
        print("\n✅ All verification tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some verification tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
