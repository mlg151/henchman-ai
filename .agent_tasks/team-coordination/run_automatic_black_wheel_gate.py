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
targets = [
    'tests/tools/test_automatic_formatting.py',
    'tests/tools/test_registry_formatting.py',
    'tests/tools/test_code_format.py',
    'tests/tools/test_python_exec_recovery.py',
    'tests/utils/test_source_files.py',
    'tests/testing/test_team_workflow_oracle.py',
    'tests/testing/test_team_package_scenario.py',
    'tests/e2e/test_coding_loop.py',
    'tests/e2e/test_team_verification_routing.py',
]
with tempfile.TemporaryDirectory(prefix='henchman-automatic-black-wheel-') as scratch:
    directory = Path(scratch)
    module.stage_workflow_tests(root, directory, include_package=True)
    subprocess.run([str(python), '-I', '-c', module._ORIGIN_CHECK], cwd=directory, env=environment, check=True, timeout=60)
    subprocess.run([str(python), '-I', '-m', 'pytest', '-p', 'pytest_asyncio.plugin', '-q', *targets], cwd=directory, env=environment, check=True, timeout=480)
    verify = '''from pathlib import Path
import importlib
import importlib.metadata
root = Path('/home/matthew/mlg-cli/src')
for name in ('henchman.tools.formatting', 'henchman.tools.registry', 'henchman.tools.builtins.code_format', 'henchman.tools.builtins.python_exec', 'henchman.utils.source_files', 'henchman.analysis.smells.scanner', 'henchman.agents.prompts'):
    module = importlib.import_module(name)
    assert Path(module.__file__).read_bytes() == root.joinpath(*name.split('.')).with_suffix('.py').read_bytes(), name
print('Installed production modules match source; Black ' + importlib.metadata.version('black'))
'''
    subprocess.run([str(python), '-I', '-c', verify], cwd=directory, env=environment, check=True, timeout=60)
