"""Extended tests for Skill command to reach 100% coverage."""

from unittest.mock import MagicMock, patch

import pytest

from henchman.cli.commands import CommandContext
from henchman.cli.commands.skill import SkillCommand
from henchman.skills.models import Skill


@pytest.fixture
def skill_command():
    return SkillCommand()

@pytest.fixture
def ctx():
    mock_ctx = MagicMock(spec=CommandContext)
    mock_ctx.console = MagicMock()
    mock_ctx.session = MagicMock()
    return mock_ctx

@pytest.mark.asyncio
async def test_skill_export(skill_command, ctx):
    with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
                mock_store = MockStore.return_value
                mock_store.export_skill.return_value = "name: test"
                ctx.args = ["export", "test"]
                await skill_command.execute(ctx)
                mock_store.export_skill.assert_called_once_with("test")
                assert ctx.console.print.called

@pytest.mark.asyncio
async def test_skill_export_not_found(skill_command, ctx):
    with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
                mock_store = MockStore.return_value
                mock_store.export_skill.side_effect = FileNotFoundError()
                ctx.args = ["export", "missing"]
                await skill_command.execute(ctx)
                assert "not found" in str(ctx.console.print.call_args)

@pytest.mark.asyncio
async def test_skill_import(skill_command, ctx, tmp_path):
        skill_file = tmp_path / "skill.yaml"
        skill_file.write_text("name: imported")
        with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
            mock_store = MockStore.return_value
            mock_skill = Skill(name="imported", description="d", steps=[])
            mock_store.import_skill.return_value = mock_skill
            ctx.args = ["import", str(skill_file)]
            await skill_command.execute(ctx)
            mock_store.import_skill.assert_called_once()
            assert "Successfully imported" in str(ctx.console.print.call_args)

@pytest.mark.asyncio
async def test_skill_import_file_not_found(skill_command, ctx):
    ctx.args = ["import", "nonexistent.yaml"]
    await skill_command.execute(ctx)
    assert "File not found" in str(ctx.console.print.call_args)

@pytest.mark.asyncio
async def test_skill_import_error(skill_command, ctx, tmp_path):
    skill_file = tmp_path / "bad.yaml"
    skill_file.write_text("bad")
    with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
        mock_store = MockStore.return_value
        mock_store.import_skill.side_effect = Exception("Import failed")
        ctx.args = ["import", str(skill_file)]
        await skill_command.execute(ctx)
        assert "Failed to import" in str(ctx.console.print.call_args)

@pytest.mark.asyncio
async def test_skill_remote_add(skill_command, ctx):
    with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
        mock_store = MockStore.return_value
        ctx.args = ["remote", "add", "url"]
        await skill_command.execute(ctx)
        mock_store.remote_add.assert_called_once_with("url")

@pytest.mark.asyncio
async def test_skill_remote_push(skill_command, ctx):
    with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
        mock_store = MockStore.return_value
        ctx.args = ["remote", "push"]
        await skill_command.execute(ctx)
        mock_store.remote_push.assert_called_once()

@pytest.mark.asyncio
async def test_skill_remote_pull(skill_command, ctx):
    with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
        mock_store = MockStore.return_value
        ctx.args = ["remote", "pull"]
        await skill_command.execute(ctx)
        mock_store.remote_pull.assert_called_once()

@pytest.mark.asyncio
async def test_skill_remote_unknown(skill_command, ctx):
    ctx.args = ["remote", "unknown"]
    await skill_command.execute(ctx)
    assert "Unknown remote command" in str(ctx.console.print.call_args)

@pytest.mark.asyncio
async def test_skill_remote_error(skill_command, ctx):
    with patch("henchman.cli.commands.skill.SkillStore") as MockStore:
        mock_store = MockStore.return_value
        mock_store.remote_push.side_effect = Exception("Git failed")
        ctx.args = ["remote", "push"]
        await skill_command.execute(ctx)
        assert "Remote operation failed" in str(ctx.console.print.call_args)
