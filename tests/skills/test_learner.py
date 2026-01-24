from henchman.core.session import SessionMessage
from henchman.providers.base import Message, ToolCall
from henchman.skills.learner import SkillLearner
from henchman.skills.models import Skill


def test_skill_learner_extract_simple():
    messages = [
        Message(role="user", content="Create a test file"),
        Message(role="assistant", content=None, tool_calls=[
            ToolCall(id="1", name="write_file", arguments={"path": "test.txt", "content": "hello"})
        ]),
        Message(role="tool", content="Success", tool_call_id="1"),
        Message(role="assistant", content="File created.")
    ]

    learner = SkillLearner()
    skill = learner.extract_skill(
        name="create-test-file",
        description="Creates a test file with hello",
        messages=messages
    )

    assert isinstance(skill, Skill)
    assert skill.name == "create-test-file"
    assert len(skill.steps) == 1
    assert skill.steps[0].tool == "write_file"
    assert skill.steps[0].arguments["path"] == "test.txt"

def test_skill_learner_extract_multiple_steps():
    messages = [
        Message(role="assistant", content=None, tool_calls=[
            ToolCall(id="1", name="ls", arguments={"path": "."})
        ]),
        Message(role="tool", content="file1.txt", tool_call_id="1"),
        Message(role="assistant", content=None, tool_calls=[
            ToolCall(id="2", name="read_file", arguments={"path": "file1.txt"})
        ]),
        Message(role="tool", content="content", tool_call_id="2"),
    ]

    learner = SkillLearner()
    skill = learner.extract_skill("list-and-read", "desc", messages)

    assert len(skill.steps) == 2
    assert skill.steps[0].tool == "ls"
    assert skill.steps[1].tool == "read_file"


def test_skill_learner_extract_session_message():

    messages = [

        SessionMessage(role="assistant", tool_calls=[{"name": "t1", "arguments": {"a": 1}}])

    ]

    learner = SkillLearner()

    skill = learner.extract_skill("name", "desc", messages)

    assert len(skill.steps) == 1

    assert skill.steps[0].tool == "t1"


