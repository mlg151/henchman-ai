"""Tests for context file loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from henchman.config.context import DEFAULT_FILENAMES, ContextLoader


class TestContextLoader:
    """Tests for ContextLoader class."""

    @pytest.fixture
    def temp_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Create a temporary home directory."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        return home

    @pytest.fixture
    def temp_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Create and change to a temporary working directory."""
        cwd = tmp_path / "workspace" / "project"
        cwd.mkdir(parents=True)
        monkeypatch.chdir(cwd)
        return cwd

    def test_no_context_files(self, temp_home: Path, temp_cwd: Path) -> None:
        """Test when no HENCHMAN.md files exist."""
        loader = ContextLoader()
        files = loader.discover_files()
        assert files == []

    def test_global_context_file(self, temp_home: Path, temp_cwd: Path) -> None:
        """Test discovering global context file."""
        henchman_dir = temp_home / ".henchman"
        henchman_dir.mkdir()
        context_file = henchman_dir / "HENCHMAN.md"
        context_file.write_text("# Global Context")

        loader = ContextLoader()
        files = loader.discover_files()
        assert len(files) == 1
        assert files[0] == context_file

    def test_workspace_context_file(self, temp_home: Path, temp_cwd: Path) -> None:
        """Test discovering workspace context file."""
        context_file = temp_cwd / "HENCHMAN.md"
        context_file.write_text("# Workspace Context")

        loader = ContextLoader()
        files = loader.discover_files()
        assert len(files) == 1
        assert files[0] == context_file

    def test_ancestor_context_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test discovering ancestor context files up to git root."""
        # Create structure: workspace/project/subdir
        workspace = tmp_path / "workspace"
        project = workspace / "project"
        subdir = project / "subdir"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)

        # Make project a git root
        (project / ".git").mkdir()

        # Create context files at different levels
        (project / "HENCHMAN.md").write_text("# Project Context")
        (subdir / "HENCHMAN.md").write_text("# Subdir Context")

        loader = ContextLoader()
        files = loader.discover_files()

        # Should find both, ordered from root to cwd
        assert len(files) == 2
        assert files[0] == project / "HENCHMAN.md"
        assert files[1] == subdir / "HENCHMAN.md"

    def test_stops_at_git_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that discovery stops at git root."""
        # Create structure: outer/inner/project
        outer = tmp_path / "outer"
        inner = outer / "inner"
        project = inner / "project"
        project.mkdir(parents=True)
        monkeypatch.chdir(project)

        # Make inner the git root
        (inner / ".git").mkdir()

        # Create context file outside git root
        (outer / "HENCHMAN.md").write_text("# Should not be found")
        (inner / "HENCHMAN.md").write_text("# Inner Context")

        loader = ContextLoader()
        files = loader.discover_files()

        # Should only find inner, not outer
        paths = [f.name for f in files]
        assert len([p for p in paths if p == "HENCHMAN.md"]) == 1
        assert inner / "HENCHMAN.md" in files

    def test_load_empty(self, temp_home: Path, temp_cwd: Path) -> None:
        """Test loading when no context files exist."""
        loader = ContextLoader()
        content = loader.load()
        assert content == ""

    def test_load_single_file(self, temp_home: Path, temp_cwd: Path) -> None:
        """Test loading a single context file."""
        context_file = temp_cwd / "HENCHMAN.md"
        context_file.write_text("# My Project\nThis is my project.")

        loader = ContextLoader()
        content = loader.load()
        assert "# My Project" in content
        assert "This is my project." in content

    def test_load_multiple_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test loading and concatenating multiple context files."""
        workspace = tmp_path / "workspace"
        project = workspace / "project"
        project.mkdir(parents=True)
        monkeypatch.chdir(project)

        (project / ".git").mkdir()
        (workspace.parent / ".henchman").mkdir(parents=True, exist_ok=True)

        # Create multiple context files
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        henchman_dir = home / ".henchman"
        henchman_dir.mkdir()
        (henchman_dir / "HENCHMAN.md").write_text("# Global Context")
        (project / "HENCHMAN.md").write_text("# Project Context")

        loader = ContextLoader()
        content = loader.load()

        assert "Global Context" in content
        assert "Project Context" in content
        # Check separator is present
        assert "---" in content

    def test_load_with_file_header(self, temp_home: Path, temp_cwd: Path) -> None:
        """Test that loaded content includes file path header."""
        context_file = temp_cwd / "HENCHMAN.md"
        context_file.write_text("# My Context")

        loader = ContextLoader()
        content = loader.load()
        # Should include context marker
        assert "Context:" in content or "HENCHMAN.md" in content

    def test_custom_filename(self, temp_home: Path, temp_cwd: Path) -> None:
        """Test using a custom filename."""
        context_file = temp_cwd / "AGENT.md"
        context_file.write_text("# Custom Context")

        loader = ContextLoader(filename="AGENT.md")
        files = loader.discover_files()
        assert len(files) == 1
        assert files[0] == context_file

    def test_subdirectory_context_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test discovering context files in subdirectories."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        monkeypatch.chdir(project)

        # Create subdirectory with context
        subdir = project / "src"
        subdir.mkdir()
        (subdir / "HENCHMAN.md").write_text("# Src Context")

        loader = ContextLoader(include_subdirs=True)
        files = loader.discover_files()

        # Should find subdirectory context
        assert subdir / "HENCHMAN.md" in files

    def test_respects_gitignore(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that gitignored directories are skipped."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        monkeypatch.chdir(project)

        # Create gitignore
        (project / ".gitignore").write_text("node_modules/\n")

        # Create context in ignored directory
        ignored = project / "node_modules"
        ignored.mkdir()
        (ignored / "HENCHMAN.md").write_text("# Should be ignored")

        loader = ContextLoader(include_subdirs=True)
        files = loader.discover_files()

        # Should not find ignored file
        assert ignored / "HENCHMAN.md" not in files


class TestContextLoaderFilename:
    """Tests for ContextLoader filename defaults and backward compat."""

    def test_default_filenames(self) -> None:
        """Test default filenames include all three instruction files."""
        loader = ContextLoader()
        assert loader.filenames == DEFAULT_FILENAMES

    def test_filename_property_returns_first(self) -> None:
        """Test filename property returns first entry for backward compat."""
        loader = ContextLoader()
        assert loader.filename == "HENCHMAN.md"

    def test_custom_single_filename(self) -> None:
        """Test passing a single custom filename."""
        loader = ContextLoader(filename="AGENT.md")
        assert loader.filenames == ("AGENT.md",)
        assert loader.filename == "AGENT.md"

    def test_custom_filenames_sequence(self) -> None:
        """Test passing a custom sequence of filenames."""
        loader = ContextLoader(filenames=["A.md", "B.md"])
        assert loader.filenames == ("A.md", "B.md")
        assert loader.filename == "A.md"


class TestContextLoaderMultipleFilenames:
    """Tests for discovering multiple context file types."""

    @pytest.fixture
    def temp_home(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        """Create a temporary home directory."""
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        return home

    def test_discovers_copilot_instructions(
        self, temp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test discovering .github/copilot-instructions.md."""
        project = tmp_path / "project"
        project.mkdir()
        monkeypatch.chdir(project)

        github_dir = project / ".github"
        github_dir.mkdir()
        copilot_file = github_dir / "copilot-instructions.md"
        copilot_file.write_text("# Copilot Instructions")

        loader = ContextLoader()
        files = loader.discover_files()
        assert copilot_file in files

    def test_discovers_gemini_md(
        self, temp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test discovering .gemini/GEMINI.md."""
        project = tmp_path / "project"
        project.mkdir()
        monkeypatch.chdir(project)

        gemini_dir = project / ".gemini"
        gemini_dir.mkdir()
        gemini_file = gemini_dir / "GEMINI.md"
        gemini_file.write_text("# Gemini Context")

        loader = ContextLoader()
        files = loader.discover_files()
        assert gemini_file in files

    def test_discovers_all_three_in_order(
        self, temp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that all three file types are discovered in priority order."""
        project = tmp_path / "project"
        project.mkdir()
        monkeypatch.chdir(project)

        # Create all three context files
        (project / "HENCHMAN.md").write_text("# Henchman")

        (project / ".github").mkdir()
        copilot = project / ".github" / "copilot-instructions.md"
        copilot.write_text("# Copilot")

        (project / ".gemini").mkdir()
        gemini = project / ".gemini" / "GEMINI.md"
        gemini.write_text("# Gemini")

        loader = ContextLoader()
        files = loader.discover_files()

        assert len(files) == 3
        assert files[0] == project / "HENCHMAN.md"
        assert files[1] == copilot
        assert files[2] == gemini

    def test_ancestor_copilot_instructions(
        self, temp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test discovering copilot-instructions.md in ancestor dir."""
        project = tmp_path / "project"
        subdir = project / "subdir"
        subdir.mkdir(parents=True)
        (project / ".git").mkdir()
        monkeypatch.chdir(subdir)

        (project / ".github").mkdir()
        copilot = project / ".github" / "copilot-instructions.md"
        copilot.write_text("# Copilot at root")

        loader = ContextLoader()
        files = loader.discover_files()
        assert copilot in files

    def test_load_concatenates_all_file_types(
        self, temp_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that load() includes content from all discovered file types."""
        project = tmp_path / "project"
        project.mkdir()
        monkeypatch.chdir(project)

        (project / "HENCHMAN.md").write_text("Henchman content")
        (project / ".gemini").mkdir()
        (project / ".gemini" / "GEMINI.md").write_text("Gemini content")

        loader = ContextLoader()
        content = loader.load()

        assert "Henchman content" in content
        assert "Gemini content" in content


class TestContextLoaderGitignore:
    """Tests for gitignore handling in ContextLoader."""

    def test_gitignore_with_comments_and_empty_lines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test gitignore parsing with comments and empty lines."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        monkeypatch.chdir(project)

        # Create gitignore with comments and empty lines
        (project / ".gitignore").write_text(
            """# This is a comment
node_modules/

# Another comment
dist
"""
        )

        # Create directories
        ignored = project / "node_modules"
        ignored.mkdir()
        (ignored / "HENCHMAN.md").write_text("# Should be ignored")

        also_ignored = project / "dist"
        also_ignored.mkdir()
        (also_ignored / "HENCHMAN.md").write_text("# Also ignored")

        loader = ContextLoader(include_subdirs=True)
        files = loader.discover_files()

        # Should not find ignored files
        assert ignored / "HENCHMAN.md" not in files
        assert also_ignored / "HENCHMAN.md" not in files

    def test_pattern_matches_first_path_component(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test pattern matching on first path component."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        monkeypatch.chdir(project)

        # Create gitignore with pattern
        (project / ".gitignore").write_text("build\n")

        # Create nested directory that matches pattern
        build_dir = project / "build"
        build_dir.mkdir()
        (build_dir / "HENCHMAN.md").write_text("# Build context")

        loader = ContextLoader(include_subdirs=True)
        files = loader.discover_files()

        # Should not find build directory
        assert build_dir / "HENCHMAN.md" not in files


class TestContextLoaderSubdirectories:
    """Tests for subdirectory handling edge cases."""

    def test_skips_non_directories(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that non-directory files are skipped."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        monkeypatch.chdir(project)

        # Create a regular file (not a directory)
        (project / "somefile.txt").write_text("content")

        # Create a valid subdirectory with HENCHMAN.md
        subdir = project / "src"
        subdir.mkdir()
        (subdir / "HENCHMAN.md").write_text("# Src context")

        loader = ContextLoader(include_subdirs=True)
        files = loader.discover_files()

        assert subdir / "HENCHMAN.md" in files

    def test_skips_hidden_directories(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that hidden directories are skipped."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        monkeypatch.chdir(project)

        # Create hidden directory
        hidden = project / ".hidden"
        hidden.mkdir()
        (hidden / "HENCHMAN.md").write_text("# Should not be found")

        loader = ContextLoader(include_subdirs=True)
        files = loader.discover_files()

        assert hidden / "HENCHMAN.md" not in files

    def test_subdirs_without_git_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test subdirs search when not in git repo."""
        project = tmp_path / "project"
        project.mkdir()
        monkeypatch.chdir(project)
        # No .git directory

        subdir = project / "src"
        subdir.mkdir()
        (subdir / "HENCHMAN.md").write_text("# Src context")

        loader = ContextLoader(include_subdirs=True)
        # Temporary directories may themselves live inside the host's repository.
        monkeypatch.setattr(loader, "_find_git_root", lambda _start: None)
        files = loader.discover_files()

        # Should not search subdirs without git root
        assert subdir / "HENCHMAN.md" not in files

    def test_subdir_without_context_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test subdirectory without HENCHMAN.md file."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        monkeypatch.chdir(project)

        # Create empty subdirectory
        subdir = project / "empty"
        subdir.mkdir()

        loader = ContextLoader(include_subdirs=True)
        files = loader.discover_files()

        # Should not fail, just not find anything
        assert subdir / "HENCHMAN.md" not in files


class TestContextLoaderIsIgnored:
    """Tests for _is_ignored method edge cases."""

    def test_path_not_relative_to_base(self) -> None:
        """Test _is_ignored when path is not relative to base."""
        loader = ContextLoader()

        # Path that cannot be made relative to base
        path = Path("/completely/different/path")
        base = Path("/some/other/base")

        result = loader._is_ignored(path, ["*"], base)
        assert result is False

    def test_pattern_matches_full_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test pattern matching on full relative path."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        monkeypatch.chdir(project)

        loader = ContextLoader()

        # Test fnmatch on full path
        path = project / "node_modules"
        result = loader._is_ignored(path, ["node_modules"], project)
        assert result is True

    def test_pattern_matches_first_component_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test pattern matching specifically on first path component."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        monkeypatch.chdir(project)

        loader = ContextLoader()

        # Create nested path where pattern matches first component
        nested = project / "build" / "output"
        nested.mkdir(parents=True)

        # Pattern "build" should match first component
        result = loader._is_ignored(nested, ["build"], project)
        assert result is True


class TestContextLoaderAncestorSearch:
    """Tests for ancestor directory search."""

    def test_no_ancestors_with_context(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test when no ancestor directories have context files."""
        project = tmp_path / "project" / "subdir"
        project.mkdir(parents=True)
        (tmp_path / "project" / ".git").mkdir()
        monkeypatch.chdir(project)

        loader = ContextLoader()
        files = loader.discover_files()

        # No context files found
        assert files == []

    def test_ancestor_search_without_git(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test ancestor search stops at cwd when not in git repo."""
        project = tmp_path / "project"
        project.mkdir()
        monkeypatch.chdir(project)

        # No .git directory - should only check cwd
        (project / "HENCHMAN.md").write_text("# Project context")

        loader = ContextLoader()
        files = loader.discover_files()

        assert project / "HENCHMAN.md" in files

    def test_no_git_does_not_search_parent_directories(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A non-repository start directory must be its own discovery boundary."""
        parent = tmp_path / "parent"
        project = parent / "project"
        project.mkdir(parents=True)
        monkeypatch.chdir(project)

        parent_context = parent / "HENCHMAN.md"
        project_context = project / "HENCHMAN.md"
        parent_context.write_text("outside project", encoding="utf-8")
        project_context.write_text("inside project", encoding="utf-8")

        loader = ContextLoader(filename="HENCHMAN.md")
        # Exercise the non-repository branch regardless of the host's temp location.
        monkeypatch.setattr(loader, "_find_git_root", lambda _start: None)
        files = loader.discover_files()

        assert project_context in files
        assert parent_context not in files

    def test_cwd_equals_git_root(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test when cwd is exactly the git root."""
        project = tmp_path / "project"
        project.mkdir()
        (project / ".git").mkdir()
        (project / "HENCHMAN.md").write_text("# Project context")
        monkeypatch.chdir(project)

        loader = ContextLoader()
        files = loader.discover_files()

        # Should find the context file at git root
        assert project / "HENCHMAN.md" in files
