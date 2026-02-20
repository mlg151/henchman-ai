
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
    settings = Settings(
        ui=UISettings(theme="dracula", show_line_numbers=False)
    )

    # Define test path
    test_path = Path("test_settings.yaml")

    try:
        # Save settings
        print(f"Saving settings to {test_path}...")
        save_settings(settings, test_path)

        # Verify file exists
        if not test_path.exists():
            print("❌ File was not created")
            return False

        # Verify content
        print("Reading back settings...")
        with open(test_path) as f:
            data = yaml.safe_load(f)

        if data.get("ui", {}).get("theme") != "dracula":
            print(f"❌ Theme mismatch. Expected 'dracula', got {data.get('ui', {}).get('theme')}")
            return False

        if data.get("ui", {}).get("show_line_numbers") is not False:
             print(f"❌ show_line_numbers mismatch. Expected False, got {data.get('ui', {}).get('show_line_numbers')}")
             return False

        print("✅ Settings persisted correctly")
        return True

    except Exception as e:
        print(f"❌ Exception: {e}")
        return False
    finally:
        # Cleanup
        if test_path.exists():
            test_path.unlink()

if __name__ == "__main__":
    success = test_settings_persistence()
    sys.exit(0 if success else 1)
