from pathlib import Path
import importlib.util
import subprocess
import tempfile
import os
import sys

root = Path('/home/matthew/mlg-cli')
python = root / '.agent_tasks/portable-wheel-env/bin/python'
location = root / 'tests/testing/installed_wheel_smoke.py'
spec = importlib.util.spec_from_file_location('wheel_smoke', location)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
environment = module.smoke_environment(dict(os.environ))
environment['UV_CACHE_DIR'] = '/tmp/henchman-uv-cache'
with tempfile.TemporaryDirectory(prefix='henchman-package-artifact-wheel-') as scratch:
    directory = Path(scratch)
    module.stage_workflow_tests(root, directory, include_package=True)
    subprocess.run([str(python), '-I', '-c', module._ORIGIN_CHECK], cwd=directory, env=environment, check=True, timeout=60)
    targets = sys.argv[1:] or ['tests/testing/test_artifact_observation.py', 'tests/testing/test_team_workflow_oracle.py', 'tests/testing/test_package_oracle.py', 'tests/testing/test_team_package_scenario.py', 'tests/testing/test_team_eval_runner.py']
    subprocess.run([str(python), '-I', '-m', 'pytest', '-p', 'pytest_asyncio.plugin', '-q', *targets], cwd=directory, env=environment, check=True, timeout=480)
