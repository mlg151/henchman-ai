from pathlib import Path
p=Path('src/henchman/advanced/plans.py')
s=p.read_text().replace('import json\n','import asyncio\nimport json\nimport os\nimport tempfile\n')
s=s.replace('from henchman.config.paths', 'from henchman.advanced.acceptance_checks import CheckSpec, parse_checks, prepare_checks, run_checks\nfrom henchman.utils.file_lock import FileLock\nfrom henchman.config.paths')
a=s.index('    raw = path.read_text'); b=s.index('\n\ndef _normalize_steps',a)
s=s[:a]+'''    with path.open("rb") as source:
        raw = source.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("Plan storage exceeds the 16 MiB limit.")
    return json.loads(raw)


def _write_json(path: Path, payload: object) -> None:
    """Atomically replace a bounded JSON index in the same directory."""
    raw = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError("Plan storage exceeds the 16 MiB limit.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as target:
            temporary = target.name
            target.write(raw)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)
''' +s[b:]
s=s.replace('    if steps:\n', '    if steps and any(not isinstance(step, str) for step in steps):\n        raise ValueError("Plan steps must be strings.")\n    if steps:\n',1)
s=s.replace('        raw_index = payload.get("index", 0)','        if not isinstance(payload.get("done", False), bool):\n            raise ValueError("Persisted step done must be a boolean.")\n        raw_index = payload.get("index", 0)')
s=s.replace('    steps: tuple[PlanStepRecord, ...]\n', '    steps: tuple[PlanStepRecord, ...]\n    checks: tuple[CheckSpec, ...] = ()\n    last_verification: dict[str, object] | None = None\n')
s=s.replace('            "steps": [step.to_dict() for step in self.steps],','            "steps": [step.to_dict() for step in self.steps],\n            "checks": [check.to_dict() for check in self.checks],\n            "last_verification": self.last_verification,')
s=s.replace('        raw_steps = payload.get("steps", [])', '''        raw_checks = payload.get("checks", [])
        if not isinstance(raw_checks, list) or len(raw_checks) > 20:
            raise ValueError("Invalid persisted acceptance checks.")
        if any(not isinstance(check, dict) for check in raw_checks):
            raise ValueError("Invalid persisted acceptance check.")
        report = payload.get("last_verification")
        if report is not None and not isinstance(report, dict):
            raise ValueError("Invalid persisted verification report.")
        raw_steps = payload.get("steps", [])''')
s=s.replace('            steps=steps,','            steps=steps,\n            checks=tuple(CheckSpec.from_dict(check) for check in raw_checks),\n            last_verification=report,',1)
s=s.replace('        self._records = self._load_records()','        self._lock_path = self._storage_dir / "verification.lock"\n        self._records = self._load_records()',1)
s=s.replace('        plan: str | None = None,\n', '        plan: str | None = None,\n        checks: object = None,\n',1)
s=s.replace('            steps=tuple(\n','            checks=prepare_checks(self._project_root, parse_checks(checks)) if checks is not None else (),\n            steps=tuple(\n',1)
s=s.replace('        self._records[record.plan_id] = record\n        self._persist_records()','        with FileLock(self._lock_path):\n            self._records = self._load_records()\n            self._records[record.plan_id] = record\n            self._persist_records()',1)
a=s.index('        record = self._require_plan(plan_id)',s.index('    def complete_step(')); b=s.index('\n    def render_status',a)
old=s[a:b].replace('        next_pending = self.next_step(plan_id)','        next_pending = next((item for item in record.steps if not item.done), None)')
s=s[:a]+'''        if isinstance(step, bool) or not isinstance(step, int):
            raise ValueError("Step must be an integer.")
        with FileLock(self._lock_path):
'''+''.join('    '+line+'\n' for line in old.rstrip().splitlines())+'''
    async def verify_plan(self, plan_id: str) -> dict[str, object]:
        """Run recorded checks and persist historical observations, not task truth."""
        run_id = uuid4().hex
        with FileLock(self._lock_path):
            record = self._require_plan(plan_id)
            if not record.checks:
                raise ValueError("This plan has no acceptance checks.")
            pending: dict[str, object] = {
                "run_id": run_id, "status": "running", "checks_passed": False,
                "task_verified": False, "checked_at": _now_iso(), "results": [],
            }
            self._records[plan_id] = replace(record, last_verification=pending)
            self._persist_records()
        try:
            report = await run_checks(self._project_root, record.checks)
        except (asyncio.CancelledError, Exception) as exc:
            failed = dict(pending, status="cancelled" if isinstance(exc, asyncio.CancelledError)
                          else "error", checked_at=_now_iso(), error=str(exc))
            self._save_report(plan_id, record.checks, run_id, failed)
            raise
        report = dict(report, run_id=run_id, status="finished", task_verified=False)
        self._save_report(plan_id, record.checks, run_id, report)
        return report

    def _save_report(
        self, plan_id: str, checks: tuple[CheckSpec, ...], run_id: str,
        report: dict[str, object],
    ) -> None:
        """Preserve concurrent step updates and reject superseded observations."""
        with FileLock(self._lock_path):
            current = self._require_plan(plan_id)
            if current.checks != checks or (current.last_verification or {}).get("run_id") != run_id:
                raise ValueError("Verification was superseded or its checks changed; run verify again.")
            self._records[plan_id] = replace(current, updated_at=_now_iso(), last_verification=report)
            self._persist_records()
''' +s[b:]
s=s.replace('        return "\\n".join(\n', '        progress = "\\n".join(\n',1)
s=s.replace('    def _require_plan', '''        report = record.last_verification
        outcome = (
            f"Historical checks: {report.get('status')}; passed={report.get('checks_passed')}; "
            f"checked_at={report.get('checked_at')}. Re-run verify after changes."
            if report else "Acceptance checks have not run."
        )
        return f"Reported step progress:\\n{progress}\\n{outcome}\\nTask verification is not established."

    def _require_plan''',1)
s=s.replace('        if not isinstance(payload, list):\n            return {}','        if not isinstance(payload, list):\n            raise ValueError("Plan storage must contain a list.")')
s=s.replace('            if not isinstance(item, dict):\n                continue','            if not isinstance(item, dict):\n                raise ValueError("Invalid persisted plan record.")')
s=s.replace('            records[record.plan_id] = record','            if not record.plan_id or record.plan_id in records:\n                raise ValueError("Missing or duplicate persisted plan identifier.")\n            records[record.plan_id] = record')
p.write_text(s)
