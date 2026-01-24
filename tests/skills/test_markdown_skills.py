from henchman.skills.models import Skill
from henchman.skills.store import SkillStore


def test_discover_workspace_skills(tmp_path):
    # Setup mock workspace
    workspace = tmp_path / "project"
    workspace.mkdir()
    skills_dir = workspace / ".github" / "skills"
    skills_dir.mkdir(parents=True)

    skill1_dir = skills_dir / "my-skill"
    skill1_dir.mkdir()
    (skill1_dir / "SKILL.md").write_text("# My Skill\nDescription here")

    # Mock CWD
    import os
    original_cwd = os.getcwd()
    os.chdir(workspace)
    try:
        store = SkillStore(skills_dir=tmp_path / "user_skills")
        found = store.discover_workspace_skills()
        assert len(found) == 1
        assert found[0].name == "SKILL.md"
        assert found[0].parent.name == "my-skill"
    finally:
        os.chdir(original_cwd)

def test_load_from_markdown_simple(tmp_path):
    store = SkillStore(skills_dir=tmp_path / "user_skills")
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("# Test Skill\nDescription")

    skill = store._load_from_markdown(skill_md)
    assert skill.name == "Test Skill"
    # Current implementation returns empty steps, which is fine for first pass
    assert isinstance(skill, Skill)
