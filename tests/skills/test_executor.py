from unittest.mock import AsyncMock

import pytest

from henchman.skills.executor import SkillExecutor
from henchman.skills.models import Skill, SkillStep
from henchman.tools.base import ToolResult
from henchman.tools.registry import ToolRegistry


@pytest.mark.asyncio
async def test_skill_executor_run():
    skill = Skill(
        name="test-skill",
        description="A test skill",
        steps=[
            SkillStep(description="s1", tool="t1", arguments={"a": 1}),
            SkillStep(description="s2", tool="t2", arguments={"b": 2}),
        ]
    )

    registry = AsyncMock(spec=ToolRegistry)
    registry.execute.side_effect = [
        ToolResult(content="r1", success=True),
        ToolResult(content="r2", success=True),
    ]

    executor = SkillExecutor(registry)
    results = []
    async for res in executor.run(skill):
        results.append(res)

    assert len(results) == 2
    assert results[0].content == "r1"
    assert results[1].content == "r2"
    assert registry.execute.call_count == 2

@pytest.mark.asyncio
async def test_skill_executor_stop_on_failure():
    skill = Skill(
        name="test-skill",
        description="A test skill",
        steps=[
            SkillStep(description="s1", tool="t1", arguments={}),
            SkillStep(description="s2", tool="t2", arguments={}),
        ]
    )

    registry = AsyncMock(spec=ToolRegistry)
    registry.execute.return_value = ToolResult(content="fail", success=False, error="err")

    executor = SkillExecutor(registry)
    results = []
    async for res in executor.run(skill):
        results.append(res)

    assert len(results) == 1
    assert results[0].success is False
    assert registry.execute.call_count == 1
