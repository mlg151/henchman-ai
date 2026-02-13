#!/usr/bin/env python3
"""
Build documentation locally for Henchman-AI.
Run this script to generate HTML documentation that can be viewed in a browser.
"""

import os
import subprocess
import sys
import webbrowser
from pathlib import Path


def check_dependencies():
    """Check if required documentation tools are installed."""
    required_packages = ["mkdocs", "mkdocs-material", "mkdocstrings[python]"]

    print("Checking documentation dependencies...")

    for package in required_packages:
        try:
            __import__(package.replace("-", "_").split("[")[0])
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} not installed")
            return False

    return True


def install_dependencies():
    """Install documentation dependencies."""
    print("Installing documentation dependencies...")

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "mkdocs",
                "mkdocs-material",
                "mkdocstrings[python]",
                "mkdocs-autorefs",
            ],
            check=True,
        )
        print("✓ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install dependencies: {e}")
        return False


def build_docs():
    """Build the documentation."""
    print("\nBuilding documentation...")

    try:
        # Build docs
        result = subprocess.run(["mkdocs", "build"], capture_output=True, text=True)

        if result.returncode == 0:
            print("✓ Documentation built successfully")
            print(f"Output directory: {os.path.abspath('site')}")

            # Check if index.html exists
            index_path = Path("site/index.html")
            if index_path.exists():
                print(f"Main page: file://{index_path.absolute()}")
                return str(index_path.absolute())
            else:
                print("⚠ index.html not found in site/ directory")
                return None
        else:
            print(f"✗ Build failed:\n{result.stderr}")
            return None

    except FileNotFoundError:
        print("✗ mkdocs command not found. Make sure it's installed.")
        return None
    except Exception as e:
        print(f"✗ Error building docs: {e}")
        return None


def serve_docs():
    """Serve documentation locally."""
    print("\nStarting documentation server...")
    print("Press Ctrl+C to stop the server")

    try:
        subprocess.run(["mkdocs", "serve"])
    except KeyboardInterrupt:
        print("\nDocumentation server stopped")
    except Exception as e:
        print(f"✗ Error serving docs: {e}")


def open_in_browser(filepath):
    """Open documentation in default browser."""
    if filepath:
        try:
            webbrowser.open(f"file://{filepath}")
            print("✓ Opened documentation in browser")
        except Exception as e:
            print(f"✗ Could not open browser: {e}")


def main():
    """Main function."""
    print("=" * 60)
    print("Henchman-AI Documentation Builder")
    print("=" * 60)

    # Check if we're in the project root
    if not Path("mkdocs.yml").exists():
        print("⚠ Warning: mkdocs.yml not found in current directory")
        print("Make sure you're in the henchman-ai project root")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != "y":
            return

    # Check/install dependencies
    if not check_dependencies():
        print("\nSome dependencies are missing.")
        response = input("Install them now? (Y/n): ")
        if response.lower() in ("", "y", "yes"):
            if not install_dependencies():
                return
        else:
            print("Cannot build documentation without dependencies.")
            return

    # Menu
    print("\nWhat would you like to do?")
    print("1. Build documentation (static HTML)")
    print("2. Serve documentation locally (live preview)")
    print("3. Build and open in browser")
    print("4. Exit")

    choice = input("\nEnter choice (1-4): ").strip()

    if choice == "1":
        build_docs()
    elif choice == "2":
        serve_docs()
    elif choice == "3":
        filepath = build_docs()
        if filepath:
            open_in_browser(filepath)
    elif choice == "4":
        print("Goodbye!")
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()
