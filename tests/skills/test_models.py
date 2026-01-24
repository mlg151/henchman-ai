from datetime import datetime

from henchman.skills.models import Skill, SkillParameter, SkillStep


def test_skill_step_model():
    step = SkillStep(
        description="Create file",
        tool="write_file",
        arguments={"path": "test.txt", "content": "hello"}
    )
    assert step.description == "Create file"
    assert step.tool == "write_file"
    assert step.arguments["path"] == "test.txt"

def test_skill_parameter_model():
    param = SkillParameter(
        description="A test parameter",
        required=True
    )
    assert param.description == "A test parameter"
    assert param.required is True
    assert param.default is None

def test_skill_model_creation():
    step = SkillStep(
        description="Step 1",
        tool="echo",
        arguments={"msg": "hello"}
    )

    skill = Skill(
        name="test-skill",
        description="A test skill",
        version=1,
        author="user",
        triggers=["run test"],
        parameters={
            "arg1": SkillParameter(description="First arg", required=True)
        },
        steps=[step]
    )

    assert skill.name == "test-skill"
    assert skill.version == 1
    assert isinstance(skill.created, datetime)
    assert len(skill.steps) == 1
    assert skill.steps[0].tool == "echo"
    assert skill.parameters["arg1"].required is True

def test_skill_defaults():
    skill = Skill(
        name="minimal-skill",
        description="Minimal",
        steps=[]
    )
    assert skill.version == 1
    assert skill.author == "system"
    assert skill.tags == []
    assert skill.triggers == []
    assert skill.parameters == {}
