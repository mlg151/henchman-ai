
import pytest

from henchman.skills.models import Skill, SkillStep
from henchman.skills.store import SkillStore


@pytest.fixture
def skill_store(tmp_path):
    return SkillStore(skills_dir=tmp_path / "skills")

def test_store_initialization(tmp_path):
    SkillStore(skills_dir=tmp_path / "skills")
    assert (tmp_path / "skills").exists()
    assert (tmp_path / "skills" / ".git").exists()

def test_save_and_load_skill(skill_store):
    skill = Skill(
        name="test-skill",
        description="A test skill",
        steps=[SkillStep(description="d", tool="t", arguments={})]
    )

    skill_store.save(skill)

    loaded = skill_store.load("test-skill")
    assert loaded.name == skill.name
    assert loaded.description == skill.description
    assert len(loaded.steps) == 1

def test_list_skills(skill_store):
    s1 = Skill(name="s1", description="d1", steps=[])
    s2 = Skill(name="s2", description="d2", steps=[])

    skill_store.save(s1)
    skill_store.save(s2)

    skills = skill_store.list_skills()
    assert len(skills) == 2
    names = {s.name for s in skills}
    assert "s1" in names
    assert "s2" in names

def test_delete_skill(skill_store):
    skill = Skill(name="to-delete", description="d", steps=[])
    skill_store.save(skill)

    assert skill_store.load("to-delete") is not None

    skill_store.delete("to-delete")

    with pytest.raises(FileNotFoundError):
        skill_store.load("to-delete")
