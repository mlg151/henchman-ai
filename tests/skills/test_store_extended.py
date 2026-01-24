
import pytest

from henchman.skills.store import SkillStore


def test_store_default_dir():
    # This might fail in CI if HOME is not writable or similar
    # But let's try to mock HOME
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("HOME", "/tmp/mockhome")
        store = SkillStore()
        assert "/tmp/mockhome/.henchman/skills" in str(store.skills_dir)

def test_delete_nonexistent_skill(tmp_path):
    store = SkillStore(skills_dir=tmp_path)
    # Should not crash
    store.delete("ghost")
