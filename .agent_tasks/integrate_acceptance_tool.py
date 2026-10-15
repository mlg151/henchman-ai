from pathlib import Path
p=Path('src/henchman/tools/builtins/tier6_tools.py');s=p.read_text()
s=s.replace('_VERIFY_PLAN_PARAMETERS: dict[str, object] = {', '''_CHECK_SCHEMAS: list[dict[str, object]] = [
    {
        "type": "object", "additionalProperties": False,
        "properties": {"kind": {"const": kind}, **properties},
        "required": ["kind", *required],
    }
    for kind, properties, required in (
        ("file_exists", {"path": {"type": "string"}}, ["path"]),
        ("file_contains", {"path": {"type": "string"},
                           "text": {"type": "string", "maxLength": 4096}}, ["path", "text"]),
        ("file_changed", {"path": {"type": "string"}}, ["path"]),
        ("command", {"argv": {"type": "array", "items": {"type": "string"},
                               "minItems": 1, "maxItems": 64},
                     "expected_exit": {"type": "integer", "default": 0},
                     "timeout": {"type": "integer", "minimum": 1, "maximum": 300}}, ["argv"]),
        ("pytest", {"path": {"type": "string"},
                    "timeout": {"type": "integer", "minimum": 1, "maximum": 300}}, ["path"]),
    )
]

_VERIFY_PLAN_PARAMETERS: dict[str, object] = {''')
s=s.replace('"enum": ["create", "next", "complete", "status", "list"]','"enum": ["create", "next", "complete", "verify", "status", "list"]')
s=s.replace('        "evidence": {"type": "string"},\n','        "evidence": {"type": "string"},\n        "checks": {"type": "array", "minItems": 1, "maxItems": 20,\n                   "items": {"oneOf": _CHECK_SCHEMAS}},\n',1)
a=s.index('class VerifyPlanExecutionTool'); b=s.index('\n\nclass LSPTool',a); sub=s[a:b]
sub=sub.replace('return "Track and verify plan execution step by step."', 'return ("Track reported plan steps and run immutable file, argv-command, or pytest checks. "\n                "Create checks before work; verify runs them. Passing checks do not establish task correctness.")')
sub=sub.replace('"""Plan verification mutates project-local state."""','"""Acceptance checks can execute project commands."""').replace('return ToolKind.WRITE','return ToolKind.EXECUTE')
sub=sub.replace('    async def execute(self, **params: object) -> ToolResult:\n', '''    async def execute(self, **params: object) -> ToolResult:
        """Return explicit validation and persistence failures to the agent."""
        try:
            return await self._execute_action(**params)
        except (KeyError, ValueError, OSError) as exc:
            return ToolResult(content=str(exc), success=False, error=str(exc))

    async def _execute_action(self, **params: object) -> ToolResult:
''')
sub=sub.replace('            steps = [str(step) for step in raw_steps] if isinstance(raw_steps, list) else None', '''            if raw_steps is not None and (
                not isinstance(raw_steps, list) or any(not isinstance(step, str) for step in raw_steps)
            ):
                raise ValueError("Plan steps must be an array of strings.")
            steps = raw_steps if isinstance(raw_steps, list) else None''')
sub=sub.replace('                    steps=steps,','                    steps=steps,\n                    checks=params.get("checks"),',1)
sub=sub.replace('        if action == "list":', '''        if action == "verify":
            if not plan_id:
                raise ValueError("A plan_id is required to run acceptance checks.")
            report = await self._plan_service.verify_plan(plan_id)
            passed = report.get("checks_passed") is True
            return ToolResult(content=json.dumps(report, sort_keys=True), success=passed,
                              error=None if passed else "Acceptance checks did not pass")

        if action == "list":''',1)
sub=sub.replace('return ToolResult(content="Plan complete.")','return ToolResult(content="All steps reported complete. Run acceptance checks to inspect results.")')
sub=sub.replace('not isinstance(step_value, int):','(not isinstance(step_value, int) or isinstance(step_value, bool)):')
s=s[:a]+sub+s[b:];p.write_text(s)
