"""Tests for compatibility-aware skill discovery."""

from __future__ import annotations

from pathlib import Path

from henchman.skills import SkillCatalog


def _write(path: Path, content: str) -> None:
    """Write a test file, creating parent directories as needed."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestSkillCatalog:
    """Tests for multi-ecosystem skill discovery."""

    def test_discovers_native_henchman_yaml_skill(self, tmp_path: Path) -> None:
        """Native `.henchman/skills/*.yaml` files should load as skills."""

        project_root = tmp_path / "workspace"
        project_root.mkdir()
        _write(
            project_root / ".henchman" / "skills" / "add-api-endpoint.yaml",
            """name: add-api-endpoint
description: Add a new REST API endpoint
steps:
  - Create route handler
  - Add tests
parameters:
  - resource: The resource name
""",
        )

        catalog = SkillCatalog(project_root=project_root, home_dir=tmp_path / "home")
        skill = catalog.get("add-api-endpoint")

        assert skill is not None
        assert skill.name == "add-api-endpoint"
        assert skill.description == "Add a new REST API endpoint"
        assert "Create route handler" in skill.instructions
        assert skill.source_kind == "henchman"

    def test_discovers_repo_bundled_skills_directory(self, tmp_path: Path) -> None:
        """The repo-root `skills/` directory should work as a bundled skill source."""

        project_root = tmp_path / "workspace"
        project_root.mkdir()
        _write(
            project_root / "skills" / "release.yaml",
            """name: release
description: Prepare a release
steps:
  - Summarize changes
""",
        )

        catalog = SkillCatalog(project_root=project_root, home_dir=tmp_path / "home")
        skill = catalog.get("release")

        assert skill is not None
        assert skill.description == "Prepare a release"
        assert skill.source_path == project_root / "skills" / "release.yaml"

    def test_discovers_claude_copilot_and_gemini_assets(self, tmp_path: Path) -> None:
        """Claude, Gemini, and Copilot workflow files should load through one catalog."""

        project_root = tmp_path / "workspace"
        project_root.mkdir()

        _write(
            project_root / ".claude" / "skills" / "deploy" / "SKILL.md",
            """---
name: deploy
description: Deploy the current branch
---
# Deploy

1. Run tests
2. Ship the build
""",
        )
        _write(
            project_root / ".gemini" / "commands" / "git" / "commit.toml",
            '''description = "Create a safe commit workflow"
prompt = """
Inspect the diff and draft a commit message.
"""
''',
        )
        _write(
            project_root / ".github" / "skills" / "linting" / "SKILL.md",
            """---
name: linting
description: Run the project linter
---
# Linting

Use the repo-standard lint commands.
""",
        )
        _write(
            project_root / ".github" / "prompts" / "release.prompt.md",
            """---
name: release-plan
description: Draft a release plan
---
# Release

Summarize the changes and release steps.
""",
        )

        catalog = SkillCatalog(project_root=project_root, home_dir=tmp_path / "home")
        names = [skill.name for skill in catalog.list_skills()]

        assert "deploy" in names
        assert "git:commit" in names
        assert "linting" in names
        assert "release-plan" in names
        assert catalog.get("deploy") is not None
        assert catalog.get("deploy").source_kind == "claude_skill"
        assert catalog.get("git:commit") is not None
        assert catalog.get("git:commit").source_kind == "gemini_command"
        assert catalog.get("linting") is not None
        assert catalog.get("linting").source_kind == "copilot_skill"
        assert catalog.get("release-plan") is not None
        assert catalog.get("release-plan").source_kind == "copilot_prompt"

    def test_project_assets_override_home_assets_by_name(self, tmp_path: Path) -> None:
        """Project-local skills should win over user/global assets with the same name."""

        home_dir = tmp_path / "home"
        project_root = tmp_path / "workspace"
        project_root.mkdir()

        _write(
            home_dir / ".claude" / "commands" / "review.md",
            """# Global Review

Review the whole repository.
""",
        )
        _write(
            project_root / ".henchman" / "skills" / "review.yaml",
            """name: review
description: Review the current change only
steps:
  - Inspect the current diff
""",
        )

        catalog = SkillCatalog(project_root=project_root, home_dir=home_dir)
        skill = catalog.get("review")

        assert skill is not None
        assert skill.source_kind == "henchman"
        assert skill.description == "Review the current change only"
        assert "current diff" in skill.instructions
