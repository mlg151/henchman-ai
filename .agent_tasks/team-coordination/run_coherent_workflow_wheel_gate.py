"""Validate the frozen coherent-workflow wheel outside the checkout."""

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
targets = ['tests/agents/test_prompts.py', 'tests/agents/test_thinking_protocol.py',
           'tests/agents/test_leader_configuration.py', 'tests/config/test_agent_overrides.py',
           'tests/agents/test_delegation_budget_disclosure.py',
           'tests/agents/test_completion_integrity.py', 'tests/cli/test_headless_loop.py',
           'tests/e2e/test_team_verification_routing.py',
           'tests/testing/test_team_environment_context.py',
           'tests/testing/test_team_eval_profile.py', 'tests/testing/test_team_workflow_oracle.py']
with tempfile.TemporaryDirectory(prefix='henchman-coherent-workflow-wheel-') as scratch:
    directory = Path(scratch)
    module.stage_workflow_tests(root, directory)
    subprocess.run([str(python), '-I', '-c', module._ORIGIN_CHECK], cwd=directory, env=environment, check=True, timeout=60)
    subprocess.run([str(python), '-I', '-m', 'pytest', '-p', 'pytest_asyncio.plugin', '-q', *targets], cwd=directory, env=environment, check=True, timeout=480)
    verify = '''from pathlib import Path
import importlib
root = Path('/home/matthew/mlg-cli/src')
for name in ('henchman.cli.prompts', 'henchman.agents.prompts', 'henchman.core.agent', 'henchman.tools.registry'):
    module = importlib.import_module(name)
    assert Path(module.__file__).read_bytes() == root.joinpath(*name.split('.')).with_suffix('.py').read_bytes(), name
print('Four installed production modules match frozen source')
'''
    subprocess.run([str(python), '-I', '-c', verify], cwd=directory, env=environment, check=True, timeout=60)
