"""Verify a clean installed sdist without provider credentials or downloads."""
import asyncio
import importlib.metadata
import os
import re
import subprocess
import sysconfig
import tempfile
from pathlib import Path
from types import SimpleNamespace

import henchman
from fastapi.testclient import TestClient
from henchman.api.server import app
from henchman.api.state import state
from henchman.advanced.tasks import TaskService
from henchman.cli.tool_manager import ToolManager
from henchman.core.goals import GoalService
from henchman.core.session_data import Session

assert importlib.metadata.version('henchman-ai') == '0.4.0'
expected = importlib.metadata.distribution('henchman-ai').locate_file('henchman/__init__.py').resolve()
assert Path(henchman.__file__).resolve() == expected

async def execution_check(root):
    session = Session(id='release-smoke', project_hash='release', started='now', last_updated='now')
    manager = ToolManager()
    manager.set_auto_approve(auto_approve=True)
    manager.bind_runtime(project_root=root, session_manager=SimpleNamespace(current=session))
    manager.register_builtin_tools()
    goal = GoalService().start(session, 'Verify the installed package')
    requests = [
        ('shell', {'command': 'echo installed > redirected.txt', 'cwd':str(root)}),
        ('python_exec', {'code':"import time; time.sleep(0.1); print('python-one')", 'cwd':str(root)}),
        ('shell', {'command': 'echo shell-two > /dev/null', 'cwd':str(root)}),
        ('python_exec', {'code':"print('python-two')", 'cwd':str(root)}),
    ]
    results = await asyncio.gather(*(manager.registry.execute(name, args) for name, args in requests))
    ids = []
    for result in results:
        assert result.success, result.content
        match = re.search(r'task-[0-9a-f]+', result.content)
        assert match, result.content
        ids.append(match.group())
    assert len(set(ids)) == 4
    service = TaskService(root)
    records = await asyncio.gather(*(service.wait_for_task(task_id, timeout=10) for task_id in ids))
    assert all(record.status == 'completed' for record in records), records
    assert (root/'redirected.txt').read_text().strip() == 'installed'
    assert 'python-one' in service.tail_output(ids[1])
    result = await manager.registry.execute('goal_status', {
        'action':'complete', 'goal_id':goal.id, 'summary':'Installed execution and redirects passed',
    })
    assert result.success, result.content
    assert GoalService().get(session).status == 'complete'

with tempfile.TemporaryDirectory(prefix='sdist-work-', dir=Path(__file__).resolve().parent) as scratch:
    root = Path(scratch)
    os.chdir(root)
    for alias in ('henchman', 'mlg'):
        exe = Path(sysconfig.get_path('scripts'))/alias
        for args, code, text in [(['--version'],0,'0.4.0'), (['--help'],0,'Commands:'), (['definitely-not-a-command'],2,'No such command')]:
            result = subprocess.run([str(exe),*args], capture_output=True, text=True, timeout=60)
            assert result.returncode == code, result.stderr
            assert text in result.stdout+result.stderr
    state.settings = SimpleNamespace(providers=SimpleNamespace(default='smoke'))
    state.agent = object()
    response = TestClient(app).get('/v1/ready')
    assert response.status_code == 200 and response.json()['agent_ready'] is True
    import chromadb
    import henchman.rag
    client = chromadb.EphemeralClient()
    collection = client.create_collection('source_smoke')
    collection.add(ids=['1'], embeddings=[[1.,0.]], documents=['operational'])
    assert collection.query(query_embeddings=[[1.,0.]],n_results=1)['ids'] == [['1']]
    asyncio.run(execution_check(root))
print('Installed sdist 0.4.0 passed: origin, CLI aliases, readiness, Chroma, redirects, four jobs, goal completion')
