"""Lint fixes obey mutation policy and automatic formatting for their target."""

from pathlib import Path

import pytest

from henchman.tools.base import ConfirmationRequest, Tool, ToolKind, ToolResult
from henchman.tools.builtins.lint_check import LintCheckTool
from henchman.tools.registry import ToolRegistry


@pytest.mark.parametrize("directory", [False, True], ids=["file", "directory"])
async def test_real_lint_fix_formats_explicit_target_outside_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, directory: bool
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    target = tmp_path / "other_project"
    target.mkdir()
    (target / "pyproject.toml").write_text("[tool.black]\nskip-string-normalization = true\n")
    source = target / "values.py"
    source.write_text("import os\nitems= [1,2]\nname= 'value'\n")
    untouched = target / "untouched.py"
    untouched.write_text("other= [3,4]\n")
    registry = ToolRegistry()
    registry.register(LintCheckTool())
    registry.add_auto_approve_policy("lint_check")

    result = await registry.execute(
        "lint_check", {"path": str(target if directory else source), "linter": "ruff", "fix": True}
    )

    assert result.success, result
    assert source.read_text() == "items = [1, 2]\nname = 'value'\n"
    assert untouched.read_text() == "other= [3,4]\n"
    assert "Black formatted 1" in result.content


async def test_plan_mode_rejects_auto_approved_lint_fix_through_child_scope(tmp_path: Path) -> None:
    source = tmp_path / "values.py"
    original = "import os\nitems= [1,2]\n"
    source.write_text(original)
    parent = ToolRegistry()
    child = ToolRegistry()
    child.inherit_policies_from(parent)
    child.register(LintCheckTool())
    child.add_auto_approve_policy("lint_check")
    parent.set_plan_mode(enabled=True)

    result = await child.execute("lint_check", {"path": str(source), "linter": "ruff", "fix": True})

    assert not result.success
    assert "Plan Mode" in result.content
    assert source.read_text() == original


async def test_check_only_lint_remains_read_only_in_plan_mode(tmp_path: Path) -> None:
    source = tmp_path / "values.py"
    original = "items= [1,2]\n"
    source.write_text(original)
    registry = ToolRegistry()
    registry.register(LintCheckTool())
    registry.set_plan_mode(enabled=True)

    result = await registry.execute("lint_check", {"path": str(source), "linter": "ruff"})

    assert result.success, result
    assert source.read_text() == original
    assert "Black formatted" not in result.content


async def test_failed_lint_fix_still_formats_partial_mutation(tmp_path: Path) -> None:
    source = tmp_path / "values.py"
    source.write_text("import os\nitems= [1,2]\nmissing()\n")
    registry = ToolRegistry()
    registry.register(LintCheckTool())
    registry.add_auto_approve_policy("lint_check")

    result = await registry.execute(
        "lint_check", {"path": str(source), "linter": "ruff", "fix": True}
    )

    assert not result.success
    assert "F821" in result.content and "missing" in result.content
    assert source.read_text() == "items = [1, 2]\nmissing()\n"
    assert "Black formatted 1" in result.content


async def test_denied_lint_fix_does_not_mutate_or_format(tmp_path: Path) -> None:
    source = tmp_path / "values.py"
    original = "import os\nitems= [1,2]\n"
    source.write_text(original)
    confirmations: list[ConfirmationRequest] = []

    async def deny(request: ConfirmationRequest) -> bool:
        confirmations.append(request)
        return False

    registry = ToolRegistry()
    registry.register(LintCheckTool())
    registry.set_confirmation_handler(deny)

    result = await registry.execute(
        "lint_check", {"path": str(source), "linter": "ruff", "fix": True}
    )

    assert not result.success
    assert "denied" in result.content.lower()
    assert len(confirmations) == 1 and confirmations[0].params is not None
    assert confirmations[0].params["path"] == str(source)
    assert source.read_text() == original


class ConditionalWrite(Tool):
    """A real extension using invocation mode while retaining a READ catalog."""

    name = "conditional_write"
    description = "Optionally update one source file."

    def execution_kind(self, params: dict[str, object]) -> ToolKind:
        return ToolKind.WRITE if params.get("write") is True else self.kind

    async def execute(self, **params: object) -> ToolResult:
        if params.get("write") is True:
            Path(str(params["path"])).write_text("value= [1,2]\n")
        return ToolResult("Finished")


@pytest.mark.parametrize("plan_mode", [False, True], ids=["confirmation", "plan-mode"])
async def test_extension_invocation_kind_controls_mutation_authorization(
    tmp_path: Path, plan_mode: bool
) -> None:
    source = tmp_path / "values.py"
    tool = ConditionalWrite()
    assert tool.kind == ToolKind.READ
    registry = ToolRegistry()
    registry.register(tool)
    registry.set_plan_mode(enabled=plan_mode)

    async def deny(_request: ConfirmationRequest) -> bool:
        return False

    registry.set_confirmation_handler(deny)
    result = await registry.execute(tool.name, {"path": str(source), "write": True})

    assert not result.success
    assert not source.exists()
