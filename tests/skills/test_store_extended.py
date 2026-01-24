
from unittest.mock import patch

import pytest

from henchman.skills.models import Skill
from henchman.skills.store import SkillStore


def test_store_default_dir():
    # This might fail in CI if HOME is not writable or similar
    # But let's try to mock HOME
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HOME", "/tmp/mockhome")
        store = SkillStore()
        assert "/tmp/mockhome/.henchman/skills" in str(store.skills_dir)

def test_export_import_skill(tmp_path):
    store = SkillStore(skills_dir=tmp_path / "skills")
    skill = Skill(name="ex", description="d", steps=[])
    store.save(skill)

    exported = store.export_skill("ex")
    assert "name: ex" in exported

    # Import into another store
    store2 = SkillStore(skills_dir=tmp_path / "skills2")
    imported = store2.import_skill(exported)
    assert imported.name == "ex"
    assert store2.load("ex").name == "ex"

def test_remote_push_pull(tmp_path):
    store = SkillStore(skills_dir=tmp_path)
    # We can't easily test real push/pull without a real remote,
    # but we can mock _run_git to verify it's called.
    with patch.object(store, "_run_git") as mock_git:
        store.remote_push()
        mock_git.assert_called_with(["push", "origin", "main"])

        store.remote_pull("upstream")
        mock_git.assert_called_with(["pull", "upstream", "main"])
