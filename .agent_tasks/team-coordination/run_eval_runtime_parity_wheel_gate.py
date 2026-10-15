"""Exercise the installed formatter and production coding loop outside source."""
from pathlib import Path
import importlib.util
import os
import subprocess
import tempfile

root = Path('/home/matthew/mlg-cli')
python = root / '.agent_tasks/portable-wheel-env/bin/python'
spec = importlib.util.spec_from_file_location('wheel_smoke', root / 'tests/testing/installed_wheel_smoke.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
environment = module.smoke_environment(dict(os.environ))
environment['UV_CACHE_DIR'] = '/tmp/henchman-uv-cache'
targets = ['tests/testing/test_team_environment_context.py', 'tests/testing/test_eval_tool_observations.py', 'tests/testing/test_eval_helpers.py', 'tests/testing/test_eval_profiles.py', 'tests/testing/test_team_eval_profile.py', 'tests/testing/test_team_eval_runner.py', 'tests/testing/test_team_workflow_oracle.py', 'tests/testing/test_team_package_scenario.py', 'tests/testing/test_counter_eval_contract.py', 'tests/testing/test_edit_eval_contract.py']
with tempfile.TemporaryDirectory(prefix='henchman-eval-runtime-parity-wheel-') as scratch:
    directory = Path(scratch)
    module.stage_workflow_tests(root, directory, include_package=True)
    subprocess.run([str(python), '-I', '-c', module._ORIGIN_CHECK], cwd=directory, env=environment, check=True, timeout=60)
    subprocess.run([str(python), '-I', '-m', 'pytest', '-p', 'pytest_asyncio.plugin', '-q', *targets], cwd=directory, env=environment, check=True, timeout=480)
    verify = '''from pathlib import Path
import importlib
import importlib.metadata
root = Path('/home/matthew/mlg-cli/src')
for name in ('henchman.config.environment', 'henchman.core.agent', 'henchman.tools.base', 'henchman.tools.builtins.lint_check', 'henchman.tools.registry', 'henchman.tools.formatting'):
    module = importlib.import_module(name)
    assert Path(module.__file__).read_bytes() == root.joinpath(*name.split('.')).with_suffix('.py').read_bytes(), name
print('Installed production modules match source; Black ' + importlib.metadata.version('black'))
'''
    subprocess.run([str(python), '-I', '-c', verify], cwd=directory, env=environment, check=True, timeout=60)
