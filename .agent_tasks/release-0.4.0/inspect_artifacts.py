"""Check exact release members and metadata without exposing file contents."""
import email
import hashlib
import json
import sys
import tarfile
import zipfile
from pathlib import Path

root = Path(sys.argv[1]).resolve()
required = {
    'henchman/core/goals.py', 'henchman/cli/commands/goal.py',
    'henchman/tools/builtins/goal_status.py', 'henchman/advanced/tasks.py',
    'henchman/cli/henchman.tcss',
}
report = []
for artifact in sorted(root.iterdir()):
    if artifact.suffix == '.whl':
        with zipfile.ZipFile(artifact) as archive:
            names = archive.namelist()
            metadata = email.message_from_bytes(archive.read(next(n for n in names if n.endswith('.dist-info/METADATA'))))
            assert required <= set(names), required - set(names)
    elif artifact.name.endswith('.tar.gz'):
        with tarfile.open(artifact) as archive:
            names = archive.getnames()
            prefix = names[0].split('/')[0]
            assert {f'{prefix}/src/{n}' for n in required} <= set(names)
            handle = archive.extractfile(f'{prefix}/PKG-INFO')
            assert handle is not None
            metadata = email.message_from_bytes(handle.read())
    else:
        continue
    assert metadata['Name'] == 'henchman-ai'
    assert metadata['Version'] == '0.4.0'
    suspicious = []
    for name in names:
        parts = Path(name).parts
        base = parts[-1]
        if any(p in {'.agent_tasks', '.henchman', '__pycache__', '.git'} for p in parts):
            suspicious.append(name)
        if base in {'.env', '.pypirc'} or base.startswith(('.env.', '.coverage')) or base.endswith(('.bak', '.backup', '.pyc')) or '.backup.' in base:
            suspicious.append(name)
    assert not suspicious, suspicious[:20]
    report.append({'filename':artifact.name, 'bytes':artifact.stat().st_size,
                   'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),
                   'members':len(names), 'version':metadata['Version']})
assert len(report) == 2
print(json.dumps(report, indent=2))
