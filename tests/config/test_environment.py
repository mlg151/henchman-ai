"""Tests for environment context detection and formatting."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from henchman.config.environment import (
    EnvironmentContext,
    _detect_available_tools,
    _detect_git_branch,
    _detect_git_root,
    _detect_git_status,
    _detect_project_types,
    _get_directory_snapshot,
    _run_cmd,
    format_environment_block,
    gather_environment,
)


class TestRunCmd:
    """Tests for the _run_cmd helper."""

    def test_successful_command(self) -> None:
        """Test running a successful command."""
        result = _run_cmd("echo", "hello")
        assert result == "hello"

    def test_failed_command(self) -> None:
        """Test running a command that fails."""
        result = _run_cmd("false")
        assert result is None

    def test_nonexistent_command(self) -> None:
        """Test running a command that doesn't exist."""
        result = _run_cmd("nonexistent_command_xyz_123")
        assert result is None

    def test_timeout(self) -> None:
        """Test command that times out."""
        with patch("henchman.config.environment._SUBPROCESS_TIMEOUT", 0.001):
            result = _run_cmd("sleep", "10")
            assert result is None


class TestDetectGitRoot:
    """Tests for git root detection."""

    def test_in_git_repo(self, tmp_path: Path) -> None:
        """Test detecting git root when in a git repo."""
        (tmp_path / ".git").mkdir()
        with patch("henchman.config.environment._run_cmd") as mock_run:
            mock_run.return_value = str(tmp_path)
            result = _detect_git_root(tmp_path)
            assert result == str(tmp_path)

    def test_not_in_git_repo(self, tmp_path: Path) -> None:
        """Test detecting git root when not in a git repo."""
        subdir = tmp_path / "no_git"
        subdir.mkdir()
        with patch("henchman.config.environment._run_cmd") as mock_run:
            mock_run.return_value = None
            result = _detect_git_root(subdir)
            assert result is None


class TestDetectGitBranch:
    """Tests for git branch detection."""

    def test_returns_string_or_none(self, tmp_path: Path) -> None:
        """Test that git branch detection returns string or None."""
        result = _detect_git_branch(tmp_path)
        assert result is None or isinstance(result, str)


class TestDetectGitStatus:
    """Tests for git status detection."""

    def test_returns_string_or_none(self, tmp_path: Path) -> None:
        """Test that git status detection returns string or None."""
        result = _detect_git_status(tmp_path)
        assert result is None or isinstance(result, str)

    def test_clean_repo(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test git status on a clean repo."""
        with patch("henchman.config.environment._run_cmd") as mock_run:
            mock_run.return_value = ""
            result = _detect_git_status(tmp_path)
            assert result == "clean (no uncommitted changes)"

    def test_few_changes(self, tmp_path: Path) -> None:
        """Test git status with few changes (shown inline)."""
        with patch("henchman.config.environment._run_cmd") as mock_run:
            mock_run.return_value = "M  src/foo.py\n?? new.txt"
            result = _detect_git_status(tmp_path)
            assert result is not None
            assert "M  src/foo.py" in result
            assert "?? new.txt" in result

    def test_many_changes_summarised(self, tmp_path: Path) -> None:
        """Test git status with many changes gets summarised."""
        lines = [f"M  file{i}.py" for i in range(8)]
        lines.extend([f"?? untracked{i}.txt" for i in range(5)])
        with patch("henchman.config.environment._run_cmd") as mock_run:
            mock_run.return_value = "\n".join(lines)
            result = _detect_git_status(tmp_path)
            assert result is not None
            assert "modified" in result
            assert "untracked" in result

    def test_git_not_available(self, tmp_path: Path) -> None:
        """Test git status when git is not available."""
        with patch("henchman.config.environment._run_cmd") as mock_run:
            mock_run.return_value = None
            result = _detect_git_status(tmp_path)
            assert result is None

    def test_summary_with_added_and_deleted(self, tmp_path: Path) -> None:
        """Test status summary includes added and deleted counts."""
        lines = [f"A  new{i}.py" for i in range(6)]
        lines.extend([f"D  old{i}.py" for i in range(4)])
        lines.append("M  changed.py")
        with patch("henchman.config.environment._run_cmd") as mock_run:
            mock_run.return_value = "\n".join(lines)
            result = _detect_git_status(tmp_path)
            assert result is not None
            assert "added" in result
            assert "deleted" in result
            assert "modified" in result

    def test_summary_with_other_category(self, tmp_path: Path) -> None:
        """Test status summary includes 'other' for non-standard statuses."""
        lines = [f"R  renamed{i}.py" for i in range(11)]
        with patch("henchman.config.environment._run_cmd") as mock_run:
            mock_run.return_value = "\n".join(lines)
            result = _detect_git_status(tmp_path)
            assert result is not None
            assert "other" in result


class TestDetectProjectTypes:
    """Tests for project type detection."""

    def test_python_project(self, tmp_path: Path) -> None:
        """Test detecting a Python project."""
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]")
        result = _detect_project_types(tmp_path)
        assert any(ptype == "Python" for ptype, _ in result)

    def test_node_project(self, tmp_path: Path) -> None:
        """Test detecting a Node.js project."""
        (tmp_path / "package.json").write_text("{}")
        result = _detect_project_types(tmp_path)
        assert any(ptype == "Node.js" for ptype, _ in result)

    def test_rust_project(self, tmp_path: Path) -> None:
        """Test detecting a Rust project."""
        (tmp_path / "Cargo.toml").write_text("[package]")
        result = _detect_project_types(tmp_path)
        assert any(ptype == "Rust" for ptype, _ in result)

    def test_go_project(self, tmp_path: Path) -> None:
        """Test detecting a Go project."""
        (tmp_path / "go.mod").write_text("module example.com/foo")
        result = _detect_project_types(tmp_path)
        assert any(ptype == "Go" for ptype, _ in result)

    def test_multiple_types(self, tmp_path: Path) -> None:
        """Test detecting multiple project types."""
        (tmp_path / "pyproject.toml").write_text("")
        (tmp_path / "Dockerfile").write_text("")
        result = _detect_project_types(tmp_path)
        types = [ptype for ptype, _ in result]
        assert "Python" in types
        assert "Docker" in types

    def test_no_markers(self, tmp_path: Path) -> None:
        """Test when no project markers are present."""
        result = _detect_project_types(tmp_path)
        assert result == []

    def test_deduplicates_types(self, tmp_path: Path) -> None:
        """Test that duplicate project types are deduplicated."""
        (tmp_path / "pyproject.toml").write_text("")
        (tmp_path / "setup.py").write_text("")
        (tmp_path / "requirements.txt").write_text("")
        result = _detect_project_types(tmp_path)
        types = [ptype for ptype, _ in result]
        assert types.count("Python") == 1

    def test_docker_compose_yaml(self, tmp_path: Path) -> None:
        """Test detecting Docker Compose with .yaml extension."""
        (tmp_path / "docker-compose.yaml").write_text("")
        result = _detect_project_types(tmp_path)
        assert any(ptype == "Docker Compose" for ptype, _ in result)

    def test_docker_compose_yml(self, tmp_path: Path) -> None:
        """Test detecting Docker Compose with .yml extension."""
        (tmp_path / "docker-compose.yml").write_text("")
        result = _detect_project_types(tmp_path)
        assert any(ptype == "Docker Compose" for ptype, _ in result)

    def test_java_maven(self, tmp_path: Path) -> None:
        """Test detecting a Java Maven project."""
        (tmp_path / "pom.xml").write_text("")
        result = _detect_project_types(tmp_path)
        assert any(ptype == "Java (Maven)" for ptype, _ in result)

    def test_java_gradle(self, tmp_path: Path) -> None:
        """Test detecting a Java Gradle project."""
        (tmp_path / "build.gradle").write_text("")
        result = _detect_project_types(tmp_path)
        assert any(ptype == "Java (Gradle)" for ptype, _ in result)

    def test_ruby_project(self, tmp_path: Path) -> None:
        """Test detecting a Ruby project."""
        (tmp_path / "Gemfile").write_text("")
        result = _detect_project_types(tmp_path)
        assert any(ptype == "Ruby" for ptype, _ in result)

    def test_php_project(self, tmp_path: Path) -> None:
        """Test detecting a PHP project."""
        (tmp_path / "composer.json").write_text("")
        result = _detect_project_types(tmp_path)
        assert any(ptype == "PHP" for ptype, _ in result)

    def test_make_project(self, tmp_path: Path) -> None:
        """Test detecting a Make project."""
        (tmp_path / "Makefile").write_text("")
        result = _detect_project_types(tmp_path)
        assert any(ptype == "Make" for ptype, _ in result)

    def test_typescript_project(self, tmp_path: Path) -> None:
        """Test detecting a TypeScript project."""
        (tmp_path / "tsconfig.json").write_text("")
        result = _detect_project_types(tmp_path)
        assert any(ptype == "TypeScript" for ptype, _ in result)


class TestGetDirectorySnapshot:
    """Tests for directory snapshot."""

    def test_basic_listing(self, tmp_path: Path) -> None:
        """Test basic directory listing."""
        (tmp_path / "src").mkdir()
        (tmp_path / "tests").mkdir()
        (tmp_path / "README.md").write_text("")
        result = _get_directory_snapshot(tmp_path)
        assert "src/" in result
        assert "tests/" in result
        assert "README.md" in result

    def test_hidden_files_excluded(self, tmp_path: Path) -> None:
        """Test that hidden files are excluded."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".env").write_text("")
        (tmp_path / "src").mkdir()
        result = _get_directory_snapshot(tmp_path)
        assert ".git/" not in result
        assert ".env" not in result
        assert "src/" in result

    def test_max_entries(self, tmp_path: Path) -> None:
        """Test that entries are capped at max_entries."""
        for i in range(50):
            (tmp_path / f"file_{i:02d}.txt").write_text("")
        result = _get_directory_snapshot(tmp_path, max_entries=5)
        assert len(result) == 5

    def test_sorted_output(self, tmp_path: Path) -> None:
        """Test that entries are sorted."""
        (tmp_path / "zebra.txt").write_text("")
        (tmp_path / "alpha.txt").write_text("")
        result = _get_directory_snapshot(tmp_path)
        assert result == sorted(result)

    def test_empty_directory(self, tmp_path: Path) -> None:
        """Test listing an empty directory."""
        result = _get_directory_snapshot(tmp_path)
        assert result == []

    def test_oserror_handling(self) -> None:
        """Test handling of OSError on inaccessible directory."""
        result = _get_directory_snapshot(Path("/nonexistent/path/xyz"))
        assert result == []


class TestDetectAvailableTools:
    """Tests for available tool detection."""

    def test_returns_list(self) -> None:
        """Test that available tools returns a list."""
        result = _detect_available_tools()
        assert isinstance(result, list)

    def test_common_tool_detected(self) -> None:
        """Test that at least one common tool is detected."""
        result = _detect_available_tools()
        # git or pip should be available in any CI/dev environment
        assert any(tool in result for tool in ("git", "pip", "python", "python3"))

    def test_with_mocked_shutil(self) -> None:
        """Test tool detection with mocked shutil.which."""
        with patch("henchman.config.environment.shutil.which") as mock_which:
            mock_which.side_effect = lambda t: "/usr/bin/" + t if t in ("git", "ruff") else None
            result = _detect_available_tools()
            assert "git" in result
            assert "ruff" in result
            assert "npm" not in result


class TestGatherEnvironment:
    """Tests for gather_environment."""

    def test_returns_frozen_dataclass(self, tmp_path: Path) -> None:
        """Test that gather_environment returns a frozen EnvironmentContext."""
        ctx = gather_environment(cwd=tmp_path)
        assert isinstance(ctx, EnvironmentContext)
        with pytest.raises(AttributeError):
            ctx.working_directory = "changed"  # type: ignore[misc]

    def test_working_directory_is_absolute(self, tmp_path: Path) -> None:
        """Test that working_directory is an absolute path."""
        ctx = gather_environment(cwd=tmp_path)
        assert Path(ctx.working_directory).is_absolute()

    def test_defaults_to_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that gather_environment defaults to Path.cwd()."""
        monkeypatch.chdir(tmp_path)
        ctx = gather_environment()
        assert ctx.working_directory == str(tmp_path.resolve())

    def test_os_info_present(self, tmp_path: Path) -> None:
        """Test that os_info is populated."""
        ctx = gather_environment(cwd=tmp_path)
        assert ctx.os_info
        assert " " in ctx.os_info  # "Linux 6.x" or "Darwin 23.x" etc

    def test_python_version_present(self, tmp_path: Path) -> None:
        """Test that python_version is populated."""
        ctx = gather_environment(cwd=tmp_path)
        assert ctx.python_version
        # Should look like "3.11.5"
        parts = ctx.python_version.split(".")
        assert len(parts) == 3

    def test_project_types_detected(self, tmp_path: Path) -> None:
        """Test that project types are detected."""
        (tmp_path / "pyproject.toml").write_text("")
        ctx = gather_environment(cwd=tmp_path)
        assert any(ptype == "Python" for ptype, _ in ctx.project_types)

    def test_directory_snapshot_populated(self, tmp_path: Path) -> None:
        """Test that directory snapshot is populated."""
        (tmp_path / "src").mkdir()
        (tmp_path / "README.md").write_text("")
        ctx = gather_environment(cwd=tmp_path)
        assert len(ctx.directory_snapshot) > 0

    def test_uses_git_root_for_inspection(self, tmp_path: Path) -> None:
        """Test that gather uses git root for project type and snapshot."""
        # Create git root with marker
        git_root = tmp_path / "repo"
        git_root.mkdir()
        (git_root / ".git").mkdir()
        (git_root / "pyproject.toml").write_text("")
        (git_root / "src").mkdir()

        # CWD is a subdirectory
        subdir = git_root / "src" / "deep"
        subdir.mkdir(parents=True)

        with patch("henchman.config.environment._detect_git_root") as mock_root:
            mock_root.return_value = str(git_root)
            ctx = gather_environment(cwd=subdir)
            # Should detect Python from git root, not subdir
            assert any(ptype == "Python" for ptype, _ in ctx.project_types)


class TestFormatEnvironmentBlock:
    """Tests for format_environment_block."""

    def test_basic_format(self) -> None:
        """Test basic formatting."""
        ctx = EnvironmentContext(
            working_directory="/home/user/project",
            git_root="/home/user/project",
            git_branch="main",
            git_status="clean (no uncommitted changes)",
            os_info="Linux 6.1.0",
            shell="/bin/bash",
            python_version="3.11.5",
            project_types=[("Python", "pyproject.toml")],
            directory_snapshot=["src/", "tests/", "README.md"],
            available_tools=["git", "python", "ruff"],
        )
        result = format_environment_block(ctx)
        assert result.startswith("<environment_context>")
        assert result.endswith("</environment_context>")
        assert "Working directory: /home/user/project" in result
        assert "Git repository root: /home/user/project" in result
        assert "Git branch: main" in result
        assert "Git status: clean" in result
        assert "OS: Linux 6.1.0" in result
        assert "Shell: /bin/bash" in result
        assert "Python: 3.11.5" in result
        assert "Python (pyproject.toml)" in result
        assert "src/ tests/ README.md" in result
        assert "git, python, ruff" in result

    def test_minimal_format(self) -> None:
        """Test formatting with minimal info (no git, no tools)."""
        ctx = EnvironmentContext(
            working_directory="/tmp/test",
            git_root=None,
            git_branch=None,
            git_status=None,
            os_info="Linux 6.1.0",
            shell=None,
            python_version="3.11.5",
        )
        result = format_environment_block(ctx)
        assert "<environment_context>" in result
        assert "Working directory: /tmp/test" in result
        assert "Git repository root" not in result
        assert "Git branch" not in result
        assert "Git status" not in result
        assert "Shell" not in result
        assert "Project type" not in result
        assert "Directory contents" not in result
        assert "Available tools" not in result
        assert "OS: Linux 6.1.0" in result
        assert "Python: 3.11.5" in result

    def test_multiple_project_types(self) -> None:
        """Test formatting with multiple project types."""
        ctx = EnvironmentContext(
            working_directory="/tmp/test",
            git_root=None,
            git_branch=None,
            git_status=None,
            os_info="Linux 6.1.0",
            shell=None,
            python_version="3.11.5",
            project_types=[("Python", "pyproject.toml"), ("Docker", "Dockerfile")],
        )
        result = format_environment_block(ctx)
        assert "Python (pyproject.toml), Docker (Dockerfile)" in result
