import sys
from pathlib import Path

import yaml

# Add src to path
sys.path.append(str(Path.cwd() / "src"))

from henchman.config.schema import Settings, UISettings
from henchman.config.settings import save_settings


def test_settings_persistence():
    print("Testing settings persistence...")

    # Create test settings
    settings = Settings(ui=UISettings(theme="dracula", show_line_numbers=False))

    # Define test path
    test_path = Path("test_settings.yaml")

    try:
        # Save settings
        print(f"Saving settings to {test_path}...")
        save_settings(settings, test_path)

        # Verify file exists
        if not test_path.exists():
            raise AssertionError("File was not created")

        # Verify content
        print("Reading back settings...")
        with open(test_path) as f:
            data = yaml.safe_load(f)

        if data.get("ui", {}).get("theme") != "dracula":
            raise AssertionError(
                f"Theme mismatch. Expected 'dracula', got {data.get('ui', {}).get('theme')}"
            )

        if data.get("ui", {}).get("show_line_numbers") is not False:
            raise AssertionError(
                "show_line_numbers mismatch. Expected False, got "
                f"{data.get('ui', {}).get('show_line_numbers')}"
            )

        print("✅ Settings persisted correctly")

    except Exception as e:
        print(f"❌ Exception: {e}")
        raise
    finally:
        # Cleanup
        if test_path.exists():
            test_path.unlink()


if __name__ == "__main__":
    test_settings_persistence()
    sys.exit(0)
