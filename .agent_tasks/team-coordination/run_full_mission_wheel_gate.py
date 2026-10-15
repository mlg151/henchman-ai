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
targets = ['tests/agents/test_delegation_mission_context.py', 'tests/e2e/test_team_mission_context.py', 'tests/agents/test_active_agent_delegation.py', 'tests/agents/test_request_capacity.py', 'tests/core/test_request_budget.py', 'tests/agents/test_delegation_budget_disclosure.py', 'tests/e2e/test_team_verification_routing.py', 'tests/testing/test_team_workflow_oracle.py']
with tempfile.TemporaryDirectory(prefix='henchman-full-mission-wheel-') as scratch:
    directory = Path(scratch)
    module.stage_workflow_tests(root, directory, include_package=True)
    subprocess.run([str(python), '-I', '-c', module._ORIGIN_CHECK], cwd=directory, env=environment, check=True, timeout=60)
    subprocess.run([str(python), '-I', '-m', 'pytest', '-p', 'pytest_asyncio.plugin', '-q', *targets], cwd=directory, env=environment, check=True, timeout=480)
    verify = '''from pathlib import Path
import importlib
import importlib.metadata
root = Path('/home/matthew/mlg-cli/src')
for name in ('henchman.agents.ledger', 'henchman.agents.orchestrator_run', 'henchman.agents.orchestrator_types', 'henchman.agents.delegation'):
    module = importlib.import_module(name)
    assert Path(module.__file__).read_bytes() == root.joinpath(*name.split('.')).with_suffix('.py').read_bytes(), name
print('Installed production modules match source; Black ' + importlib.metadata.version('black'))
'''
    subprocess.run([str(python), '-I', '-c', verify], cwd=directory, env=environment, check=True, timeout=60)
