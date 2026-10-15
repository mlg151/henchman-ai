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
with tempfile.TemporaryDirectory(prefix='henchman-proportional-handoff-wheel-') as scratch:
    directory = Path(scratch)
    module.stage_workflow_tests(root, directory)
    subprocess.run([str(python), '-I', '-c', module._ORIGIN_CHECK], cwd=directory, env=environment, check=True, timeout=60)
    for alias in ('henchman', 'mlg'):
        for arguments, expected_code, expected_text in (
            (['--version'], 0, 'version'), (['--help'], 0, 'Commands:'),
            (['definitely-not-a-command'], 2, "No such command 'definitely-not-a-command'"),
        ):
            result = subprocess.run([str(python.parent / alias), *arguments], cwd=directory, env=environment, capture_output=True, timeout=60)
            assert result.returncode == expected_code, result.stderr
            assert expected_text.encode('ascii') in result.stdout + result.stderr
            print(f'Verified {alias} {arguments}', flush=True)
    subprocess.run([str(python), '-I', '-c', module._RAG_CHECK], cwd=directory, env=environment, check=True, timeout=120)
    subprocess.run([str(python), '-I', '-m', 'pytest', '-p', 'pytest_asyncio.plugin', '-q', 'tests/'], cwd=directory, env=environment, check=True, timeout=600)
