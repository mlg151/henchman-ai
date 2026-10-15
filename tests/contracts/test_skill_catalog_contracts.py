"""Contract tests for SkillCatalog behavioral boundaries.

These tests enforce the discovery, resolution, and precedence contracts of the
SkillCatalog component, ensuring stable behavior across skill ecosystem formats.
"""

from __future__ import annotations

import tempfile
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from henchman.skills.catalog import (
    SkillCatalog,
    SkillDefinition,
    _name_from_relative_path,
    _parse_markdown_asset,
    _render_native_skill_instructions,
    _render_parameters,
)

# ---------------------------------------------------------------------------
# SkillDefinition contracts
# ---------------------------------------------------------------------------


class TestSkillDefinitionContract:
    """Contract tests for SkillDefinition dataclass."""

    def test_all_fields_present(self) -> None:
        """SkillDefinition should have all required fields."""
        skill = SkillDefinition(
            name="test_skill",
            description="A test skill",
            instructions="Do something",
            source_path=Path("/tmp/test.yml"),
            source_kind="henchman",
        )
        assert skill.name == "test_skill"
        assert skill.description == "A test skill"
        assert skill.instructions == "Do something"
        assert skill.source_kind == "henchman"

    def test_frozen(self) -> None:
        """SkillDefinition should be immutable."""
        skill = SkillDefinition(
            name="test", description="desc", instructions="inst",
            source_path=Path("/tmp"), source_kind="henchman",
        )
        with pytest.raises(FrozenInstanceError):
            skill.name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SkillCatalog discovery contracts
# ---------------------------------------------------------------------------


class TestSkillCatalogContract:
    """Contract tests for SkillCatalog discovery and resolution."""

    @pytest.fixture
    def tmp_dir(self) -> Path:
        tmp = Path(tempfile.mkdtemp())
        yield tmp
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    def test_list_skills_empty(self, tmp_dir: Path) -> None:
        """list_skills should return empty list when no skills found."""
        catalog = SkillCatalog(project_root=tmp_dir, home_dir=tmp_dir)
        skills = catalog.list_skills()
        assert skills == []

    def test_discover_yaml_skills(self, tmp_dir: Path) -> None:
        """Catalog should discover YAML skills from the project skills directory."""
        skills_dir = tmp_dir / "skills"
        skills_dir.mkdir()
        (skills_dir / "my_skill.yml").write_text(
            "name: My Skill\ndescription: Does things\nsteps: [Step 1, Step 2]",
        )
        catalog = SkillCatalog(project_root=tmp_dir, home_dir=tmp_dir)
        skills = catalog.list_skills()
        assert len(skills) == 1
        assert skills[0].name == "My Skill"
        assert skills[0].description == "Does things"
        assert skills[0].source_kind == "henchman"

    def test_discover_markdown_skills(self, tmp_dir: Path) -> None:
        """Catalog should discover Markdown skills from .claude/skills directory."""
        skills_dir = tmp_dir / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        skill_dir = skills_dir / "code_review"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: Code Review\ndescription: Reviews code\n---\n\nRead the code and provide feedback.",
        )
        catalog = SkillCatalog(project_root=tmp_dir, home_dir=tmp_dir)
        skills = catalog.list_skills()
        assert len(skills) == 1
        assert skills[0].name == "Code Review"
        assert skills[0].source_kind == "claude_skill"

    def test_discover_gemini_commands(self, tmp_dir: Path) -> None:
        """Catalog should discover Gemini TOML commands."""
        gemini_dir = tmp_dir / ".gemini" / "commands"
        gemini_dir.mkdir(parents=True)
        (gemini_dir / "summarize.toml").write_text(
            'name = "Summarize"\ndescription = "Summarizes text"\nprompt = "Read and summarize"',
        )
        catalog = SkillCatalog(project_root=tmp_dir, home_dir=tmp_dir)
        skills = catalog.list_skills()
        assert len(skills) == 1
        assert skills[0].name == "Summarize"
        assert skills[0].source_kind == "gemini_command"

    def test_project_local_takes_precedence(self, tmp_dir: Path) -> None:
        """Project-local skills should override home skills with the same name."""
        home_dir = tmp_dir / "home"
        project_dir = tmp_dir / "project"
        home_dir.mkdir()
        project_dir.mkdir()

        # Home skill
        home_skills = home_dir / ".henchman" / "skills"
        home_skills.mkdir(parents=True)
        (home_skills / "shared.yml").write_text(
            "name: Shared\ndescription: Home version",
        )
        # Project skill with same name
        proj_skills = project_dir / "skills"
        proj_skills.mkdir(parents=True)
        (proj_skills / "shared.yml").write_text(
            "name: Shared\ndescription: Project version",
        )
        catalog = SkillCatalog(project_root=project_dir, home_dir=home_dir)
        skills = catalog.list_skills()
        # Project version should win (discovered last = highest precedence)
        assert len(skills) == 1
        # The project version overwrites the home version due to casefolded key
        assert skills[0].source_path.parent == proj_skills
        assert "Project version" in skills[0].description

    def test_get_case_insensitive(self, tmp_dir: Path) -> None:
        """get() should resolve skills case-insensitively."""
        skills_dir = tmp_dir / "skills"
        skills_dir.mkdir()
        (skills_dir / "my_skill.yml").write_text(
            "name: MySkill\ndescription: Test",
        )
        catalog = SkillCatalog(project_root=tmp_dir, home_dir=tmp_dir)
        assert catalog.get("myskill") is not None
        assert catalog.get("MYSKILL") is not None
        assert catalog.get("MySkill") is not None
        assert catalog.get("nonexistent") is None

    def test_list_skills_sorted_by_name(self, tmp_dir: Path) -> None:
        """list_skills should return skills sorted alphabetically by name."""
        skills_dir = tmp_dir / "skills"
        skills_dir.mkdir()
        (skills_dir / "c_skill.yml").write_text("name: Charlie\ndescription: C")
        (skills_dir / "a_skill.yml").write_text("name: Alpha\ndescription: A")
        (skills_dir / "b_skill.yml").write_text("name: Bravo\ndescription: B")
        catalog = SkillCatalog(project_root=tmp_dir, home_dir=tmp_dir)
        skills = catalog.list_skills()
        names = [s.name for s in skills]
        assert names == ["Alpha", "Bravo", "Charlie"]

    def test_set_project_root(self, tmp_dir: Path) -> None:
        """set_project_root should update the discovery root."""
        catalog = SkillCatalog(project_root=tmp_dir, home_dir=tmp_dir)
        new_root = Path(tempfile.mkdtemp())
        try:
            skills_dir = new_root / "skills"
            skills_dir.mkdir()
            (skills_dir / "new.yml").write_text("name: NewRoot\ndescription: From new root")
            catalog.set_project_root(new_root)
            skills = catalog.list_skills()
            assert len(skills) == 1
            assert skills[0].name == "NewRoot"
        finally:
            import shutil
            shutil.rmtree(new_root, ignore_errors=True)

    def test_nonexistent_directory_skipped(self, tmp_dir: Path) -> None:
        """Discovery should silently skip non-existent directories."""
        catalog = SkillCatalog(project_root=tmp_dir / "nonexistent", home_dir=tmp_dir / "alsonothome")
        skills = catalog.list_skills()
        assert skills == []

    def test_malformed_yaml_skill_uses_filename(self, tmp_dir: Path) -> None:
        """A YAML skill without a name field should use the filename."""
        skills_dir = tmp_dir / "skills"
        skills_dir.mkdir()
        (skills_dir / "unnamed_skill.yml").write_text("description: No name field")
        catalog = SkillCatalog(project_root=tmp_dir, home_dir=tmp_dir)
        skills = catalog.list_skills()
        assert len(skills) == 1
        assert skills[0].name == "unnamed_skill"

    def test_empty_yaml_file_produces_skill_with_empty_description(self, tmp_dir: Path) -> None:
        """An empty YAML file should produce a skill with empty description."""
        skills_dir = tmp_dir / "skills"
        skills_dir.mkdir()
        (skills_dir / "empty.yml").write_text("")
        catalog = SkillCatalog(project_root=tmp_dir, home_dir=tmp_dir)
        skills = catalog.list_skills()
        assert len(skills) == 1
        assert skills[0].name == "empty"
        assert skills[0].description == ""


# ---------------------------------------------------------------------------
# _name_from_relative_path contracts
# ---------------------------------------------------------------------------


class TestNameFromRelativePathContract:
    """Contract tests for path-to-name conversion."""

    def test_strips_suffix(self) -> None:
        """Suffix should be stripped from the path."""
        name = _name_from_relative_path(Path("foo/bar.toml"), suffixes=(".toml",))
        assert name == "foo:bar"

    def test_strips_multiple_suffixes(self) -> None:
        """Should strip the matching suffix from multiple options."""
        name = _name_from_relative_path(Path("foo/bar.prompt.md"), suffixes=(".prompt.md", ".md"))
        assert name == "foo:bar"

    def test_no_match_keeps_path(self) -> None:
        """When no suffix matches, the full path is kept."""
        name = _name_from_relative_path(Path("foo/bar.txt"), suffixes=(".toml",))
        assert name == "foo:bar.txt"

    def test_slashes_become_colons(self) -> None:
        """Path separators should be converted to colons."""
        name = _name_from_relative_path(Path("a/b/c"), suffixes=())
        assert name == "a:b:c"


# ---------------------------------------------------------------------------
# _parse_markdown_asset contracts
# ---------------------------------------------------------------------------


class TestParseMarkdownAssetContract:
    """Contract tests for YAML frontmatter parsing."""

    def test_parses_frontmatter(self) -> None:
        """Should extract YAML frontmatter and body."""
        text = "---\nname: Test\ndescription: A test\n---\n\nBody content here."
        metadata, body = _parse_markdown_asset(text)
        assert metadata["name"] == "Test"
        assert metadata["description"] == "A test"
        assert body == "Body content here."

    def test_no_frontmatter_returns_full_body(self) -> None:
        """Text without frontmatter should return empty metadata and full text as body."""
        text = "Just plain text, no frontmatter."
        metadata, body = _parse_markdown_asset(text)
        assert metadata == {}
        assert body == "Just plain text, no frontmatter."

    def test_incomplete_frontmatter_returns_body(self) -> None:
        """Frontmatter without closing delimiter should return full text as body."""
        text = "---\nname: Test\nNo closing delimiter."
        metadata, body = _parse_markdown_asset(text)
        assert metadata == {}
        assert "name: Test" in body

    def test_empty_frontmatter(self) -> None:
        """Empty frontmatter block should return empty metadata."""
        text = "---\n---\n\nBody."
        metadata, body = _parse_markdown_asset(text)
        assert metadata == {}
        assert body == "Body."

    def test_non_dict_frontmatter(self) -> None:
        """Non-dict YAML frontmatter should return empty metadata."""
        text = "---\n- item1\n- item2\n---\n\nBody."
        metadata, body = _parse_markdown_asset(text)
        assert metadata == {}
        assert body == "Body."


# ---------------------------------------------------------------------------
# _render_native_skill_instructions contracts
# ---------------------------------------------------------------------------


class TestRenderNativeSkillInstructionsContract:
    """Contract tests for native skill instruction rendering."""

    def test_renders_steps(self) -> None:
        """Steps list should be rendered as numbered list."""
        payload = {"steps": ["First", "Second", "Third"]}
        result = _render_native_skill_instructions(payload)
        assert "1. First" in result
        assert "2. Second" in result
        assert "3. Third" in result

    def test_renders_parameters(self) -> None:
        """Parameters list should be rendered."""
        payload = {"parameters": ["file", "mode"]}
        result = _render_native_skill_instructions(payload)
        assert "Parameters:" in result
        assert "- file" in result
        assert "- mode" in result

    def test_renders_dict_parameters(self) -> None:
        """Dict parameters should be rendered as key: value."""
        payload = {"parameters": [{"file": "The file to process"}, {"mode": "Read or write"}]}
        result = _render_native_skill_instructions(payload)
        assert "- file: The file to process" in result
        assert "- mode: Read or write" in result

    def test_renders_steps_and_parameters(self) -> None:
        """Both steps and parameters should be rendered together."""
        payload = {"steps": ["Do it"], "parameters": ["arg1"]}
        result = _render_native_skill_instructions(payload)
        assert "Steps:" in result
        assert "Parameters:" in result

    def test_falls_back_to_description(self) -> None:
        """With no steps or parameters, should use description."""
        payload = {"description": "Just a description"}
        result = _render_native_skill_instructions(payload)
        assert result == "Just a description"

    def test_empty_payload(self) -> None:
        """Empty payload should return empty string."""
        result = _render_native_skill_instructions({})
        assert result == ""

    def test_empty_steps_skipped(self) -> None:
        """Empty steps list should be skipped."""
        payload = {"steps": []}
        result = _render_native_skill_instructions(payload)
        assert result == ""


# ---------------------------------------------------------------------------
# _render_parameters contracts
# ---------------------------------------------------------------------------


class TestRenderParametersContract:
    """Contract tests for parameter rendering."""

    def test_empty_parameters(self) -> None:
        """Empty/None parameters should return empty list."""
        assert _render_parameters(None) == []
        assert _render_parameters([]) == []

    def test_string_parameters(self) -> None:
        """String parameters should be rendered as bullet points."""
        result = _render_parameters(["file", "mode"])
        assert result == ["Parameters:", "- file", "- mode"]

    def test_dict_parameters(self) -> None:
        """Dict parameters should render key: value pairs."""
        result = _render_parameters([{"name": "The name"}, {"count": 5}])
        assert "Parameters:" in result
        assert "- name: The name" in result
        assert "- count: 5" in result

    def test_mixed_parameters(self) -> None:
        """Mixed string and dict parameters should both render."""
        result = _render_parameters(["file", {"mode": "r/w"}])
        assert "- file" in result
        assert "- mode: r/w" in result
