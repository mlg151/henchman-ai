import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from henchman.config.repository import SettingsRepository
from henchman.config.settings import SettingsSnapshot, load_settings_snapshot


class TestGroupedSettingsInspection(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.test_dir = Path(temporary.name).resolve()
        self.project_root = self.test_dir / "project"
        home = self.test_dir / "home"
        home.mkdir()
        home_patch = patch.object(Path, "home", return_value=home)
        home_patch.start()
        self.addCleanup(home_patch.stop)
        environment_patch = patch.dict(os.environ, {})
        environment_patch.start()
        self.addCleanup(environment_patch.stop)

        self.henchman_dir = self.project_root / ".henchman"
        self.henchman_dir.mkdir(parents=True, exist_ok=True)

        os.environ.pop("HENCHMAN_PROVIDER", None)
        os.environ.pop("HENCHMAN_MODEL", None)
        os.environ.pop("HENCHMAN_SETTINGS_PATH", None)

    def test_grouped_settings_inspection(self) -> None:
        settings_file = self.henchman_dir / "settings.yaml"
        with open(settings_file, "w", encoding="utf-8") as f:
            f.write("providers:\n")
            f.write("  deepseek:\n")
            f.write("    api_key: dummy-api-key\n")
            f.write("    model: project-model\n")

        os.environ["HENCHMAN_PROVIDER"] = "deepseek"
        os.environ["HENCHMAN_MODEL"] = "snapshot-model"

        repository = SettingsRepository(project_root=self.project_root)

        captured_snapshot = load_settings_snapshot(project_root=self.project_root)

        call_count = 0
        calls: list[Path | None] = []

        def mock_load_snapshot(project_root: Path | None = None) -> SettingsSnapshot:
            nonlocal call_count
            calls.append(project_root)
            call_count += 1
            return captured_snapshot

        with patch(
            "henchman.config.repository.load_settings_snapshot", side_effect=mock_load_snapshot
        ):
            os.environ["HENCHMAN_MODEL"] = "different-model"
            with open(settings_file, "w", encoding="utf-8") as f:
                f.write("providers:\n")
                f.write("  deepseek:\n")
                f.write("    api_key: different-api-key\n")

            inspection_results = repository.inspect(include_groups=True)

            self.assertEqual(call_count, 1)
            self.assertEqual(calls, [self.project_root])

            self.assertIn("providers.deepseek", inspection_results)
            deepseek_inspection = inspection_results["providers.deepseek"]

            self.assertEqual(deepseek_inspection.value["model"], "snapshot-model")
            self.assertEqual(deepseek_inspection.value["api_key"], "dummy-api-key")
            self.assertEqual(deepseek_inspection.origin.scope, "mixed")
            self.assertIsNone(deepseek_inspection.origin.source)

            self.assertIn("providers.deepseek.model", inspection_results)
            model_origin = inspection_results["providers.deepseek.model"].origin
            self.assertEqual(model_origin.scope, "environment")
            self.assertEqual(model_origin.source, "HENCHMAN_MODEL")

            self.assertIn("providers.deepseek.api_key", inspection_results)
            api_key_origin = inspection_results["providers.deepseek.api_key"].origin
            self.assertEqual(api_key_origin.scope, "project")
            self.assertEqual(api_key_origin.source, str(settings_file))

            call_count = 0
            calls.clear()

            default_inspection = repository.inspect()
            self.assertNotIn("providers.deepseek", default_inspection)
            self.assertIn("providers.deepseek.model", default_inspection)
            self.assertIn("providers.deepseek.api_key", default_inspection)

            self.assertEqual(call_count, 1)
            self.assertEqual(calls, [self.project_root])
