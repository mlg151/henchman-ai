"""Re-stage current fixtures and rerun the exact repaired installed checks."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

base=Path(__file__).resolve().parent
repository=base.parents[1]
spec=importlib.util.spec_from_file_location('wheel_smoke',repository/'tests/testing/installed_wheel_smoke.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
work=base/f'installed-tests-{sys.argv[1]}'
work.mkdir(exist_ok=True)
module.stage_workflow_tests(repository,work)
python=base/f'venv-wheel{sys.argv[1]}'/'bin/python'
result=subprocess.run([
    str(python),'-I','-m','pytest','-p','pytest_asyncio.plugin','-q',
    'tests/testing/test_eval_profiles.py::test_engineer_real_checker_failure_then_repair_is_visible',
    'tests/testing/test_team_workflow_oracle.py::test_late_execution_edit_requires_fresh_tests_and_review',
    'tests/tools/test_automatic_formatting.py::test_missing_black_fails_explicitly_without_installation',
],cwd=work,env=module.smoke_environment(dict(os.environ)))
sys.exit(result.returncode)
