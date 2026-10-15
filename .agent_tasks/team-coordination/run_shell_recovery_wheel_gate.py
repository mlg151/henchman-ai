from pathlib import Path
import importlib.util
import subprocess
import tempfile
import os

root = Path('/home/matthew/mlg-cli')
python = root / '.agent_tasks/portable-wheel-env/bin/python'
location = root / 'tests/testing/installed_wheel_smoke.py'
spec = importlib.util.spec_from_file_location('wheel_smoke', location)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
environment = module.smoke_environment(dict(os.environ))
with tempfile.TemporaryDirectory(prefix='henchman-shell-recovery-wheel-') as scratch:
    directory = Path(scratch)
    module.stage_workflow_tests(root, directory)
    subprocess.run([str(python), '-I', '-c', module._ORIGIN_CHECK], cwd=directory, env=environment, check=True, timeout=60)
    subprocess.run([str(python), '-I', '-m', 'pytest', '-p', 'pytest_asyncio.plugin', '-q', 'tests/tools/test_shell_recovery_guidance.py', 'tests/tools/test_shell_quoted_python.py', 'tests/tools/test_shell_portability.py', 'tests/e2e/test_coding_loop.py', 'tests/e2e/test_team_verification_routing.py'], cwd=directory, env=environment, check=True, timeout=300)
    subprocess.run([str(python), '-I', '-c', "from pathlib import Path; import henchman.tools.builtins.shell as module; assert Path(module.__file__).read_bytes() == Path('/home/matthew/mlg-cli/src/henchman/tools/builtins/shell.py').read_bytes(); print('Installed shell module matches source')"], cwd=directory, env=environment, check=True, timeout=30)
