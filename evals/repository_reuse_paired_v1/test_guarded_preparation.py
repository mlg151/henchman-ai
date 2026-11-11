"""Exercise retrieval under the same offline process restrictions as a worker."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


class GuardedPreparationTests(unittest.TestCase):
    def test_real_searches_work_without_widening_subprocess_or_network_access(self):
        script = textwrap.dedent('''
            import asyncio, json, os, subprocess, sys
            from pathlib import Path
            import contract as c, fixtures
            from worker_guard import allowed_subprocess, bind_guard
            from worker_support import prepare_retrieval
            from henchman.tools.builtins.pattern_search import PatternSearchTool
            from henchman.tools.registry import ToolRegistry

            root=Path(sys.argv[1]).resolve()
            spec=fixtures.prepare(root,'labels')
            env=dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1',
                     GIT_AUTHOR_DATE='2000-01-01T00:00:00+0000', GIT_COMMITTER_DATE='2000-01-01T00:00:00+0000')
            commands=[['git','init','-q','-b','reuse-eval'],['git','config','user.name','Offline Fixture'],
                      ['git','config','user.email','offline@example.invalid'],['git','add','.'],
                      ['git','-c','commit.gpgsign=false','-c','core.hooksPath=/dev/null','commit','-qm','fixture']]
            for command in commands:
                subprocess.run(command,cwd=root,env=env,check=True,timeout=15,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            os.chdir(root)
            denials=[]; searches=[]
            def audit(event, args):
                if event in ('socket.connect','socket.connect_ex'):
                    raise c.Denied('offline network forbidden')
                if event == 'subprocess.Popen' and not allowed_subprocess(args[1],args[2],root,'labels',c.HERE/'checker.py',sys.executable):
                    denials.append(list(args[1]))
                    raise c.Denied('subprocess outside fixed bounds')
            sys.addaudithook(audit)
            async def run():
                registry=ToolRegistry();registry.register(PatternSearchTool(project_root=root))
                bind_guard(registry,root,'labels','held-plan',[],searches)
                out=[await prepare_retrieval(registry,'labels',arm) for arm in ('baseline','repository')]
                assert all(item['status']=='complete' and spec['helper_path'] in item['content'] for item in out)
                # Registry policy can invoke the guard more than once per tool call.
                assert {item['strategy'] for item in searches} == {'combined','repository'},searches
                assert not denials,denials
                print(json.dumps({'statuses':[item['status'] for item in out], 'denied':denials}))
            asyncio.run(run())
        ''')
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve()
            env = dict(os.environ, HOME=str(root), USERPROFILE=str(root),
                       XDG_CONFIG_HOME=str(root/'config'), PYTHONDONTWRITEBYTECODE='1')
            result = subprocess.run([sys.executable, '-B', '-c', script, str(root/'workspace')],
                                    env=env, capture_output=True, text=True, timeout=60, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['denied'], [])
