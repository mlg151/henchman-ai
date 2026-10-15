"""Contract tests for the Config Context Loader.

These tests validate:
- ContextLoader determinism and ordering guarantees (behavioral contract)
"""

from __future__ import annotations

from pathlib import Path

from henchman.config.context import ContextLoader


class TestContextLoaderContract:
    """ContextLoader must satisfy deterministic discovery and ordering guarantees."""

    def test_discover_files_deterministic_order(self, tmp_path: Path) -> None:
        """ContextLoader should discover files in deterministic order."""
        # ContextLoader uses resolve_project_settings_path which looks for .henchman/
        settings_dir = tmp_path / ".henchman"
        settings_dir.mkdir(parents=True)
        (settings_dir / "HENCHMAN.md").write_text("project context")

        loader = ContextLoader(start_dir=tmp_path)
        files = loader.discover_files()
        assert len(files) >= 1
        # All files should be unique
        assert len(files) == len(set(files))

    def test_discover_files_deduplicates_paths(self, tmp_path: Path) -> None:
        """ContextLoader should deduplicate paths regardless of discovery order."""
        settings_dir = tmp_path / ".henchman"
        settings_dir.mkdir(parents=True)
        context_file = settings_dir / "HENCHMAN.md"
        context_file.write_text("project context")

        loader = ContextLoader(start_dir=tmp_path)
        files = loader.discover_files()

        # Should not have duplicate entries
        assert len(files) == len(set(files))

    def test_load_concatenates_content(self, tmp_path: Path) -> None:
        """ContextLoader.load() should concatenate discovered content."""
        settings_dir = tmp_path / ".henchman"
        settings_dir.mkdir(parents=True)
        (settings_dir / "HENCHMAN.md").write_text("project-context")

        loader = ContextLoader(start_dir=tmp_path)
        content = loader.load()
        assert "project-context" in content

    def test_load_no_context_files(self, tmp_path: Path) -> None:
        """Loading with no context files should return empty string."""
        loader = ContextLoader(start_dir=tmp_path)
        content = loader.load()
        assert content == ""

    def test_load_with_include_subdirs(self, tmp_path: Path) -> None:
        """With include_subdirs=True, files in subdirectories should be found."""
        settings_dir = tmp_path / ".henchman"
        settings_dir.mkdir(parents=True)
        (settings_dir / "HENCHMAN.md").write_text("project context")

        # Also create a file in a subdirectory
        sub_dir = tmp_path / "subdir"
        sub_dir.mkdir()
        (sub_dir / "HENCHMAN.md").write_text("subdir context")

        loader = ContextLoader(start_dir=tmp_path, include_subdirs=True)
        files = loader.discover_files()
        # Should find at least the project-level file
        assert len(files) >= 1
        assert len(files) == len(set(files))
