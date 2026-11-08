"""Fixed-path tool guard for repository reuse attempts."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
import sys

import fixtures
from henchman.config.schema import Settings
from henchman.tools.builtins.file_edit import EditFileTool
from henchman.tools.builtins.file_read import ReadFileTool
from henchman.tools.builtins.file_write import WriteFileTool
from henchman.tools.builtins.pattern_search import PatternSearchTool
from henchman.tools.builtins.tier6_tools import VerifyPlanExecutionTool
from henchman.tools.registry import ToolRegistry
from worker_guard import allowed_subprocess, bind_guard


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.previous = Path.cwd()
        self.spec = fixtures.prepare(self.root, 'labels')
        os.chdir(self.root)
        self.registry = ToolRegistry()
        self.read, self.write, self.edit = ReadFileTool(), WriteFileTool(), EditFileTool()
        self.search, self.verify = PatternSearchTool(project_root=self.root), VerifyPlanExecutionTool(settings=Settings())
        for tool in (self.read, self.write, self.edit, self.search, self.verify):
            self.registry.register(tool)
        self.denials = []
        self.searches = []
        self.guard = bind_guard(self.registry, self.root, 'labels', 'held-plan', self.denials, self.searches)

    def tearDown(self):
        os.chdir(self.previous)
        self.temp.cleanup()

    def test_exact_read_write_and_verifier_scope(self):
        self.assertIsNone(self.guard(self.read, {'path': self.spec['helper_path']}))
        self.assertIsNone(self.guard(self.write, {'path': self.spec['target'], 'content': 'text'}))
        self.assertIsNone(self.guard(self.verify, {'action': 'verify', 'plan_id': 'held-plan'}))
        self.assertFalse(self.guard(self.write, {'path': self.spec['helper_path'], 'content': 'text'}).success)
        self.assertFalse(self.guard(self.read, {'path': '../outside'}).success)
        self.assertFalse(self.guard(self.verify, {'action': 'verify', 'plan_id': 'other'}).success)

    def test_parent_traversal_is_refused_before_normalization(self):
        target = Path(self.spec['target'])
        traversal = str(target.parent / '..' / target)
        outside = Path(self.temp.name).parent
        (self.root / 'alias').symlink_to(outside, target_is_directory=True)
        aliased = str(Path('alias') / '..' / target)
        for path in (traversal, aliased):
            with self.subTest(path=path):
                result = self.guard(self.write, {'path': path, 'content': 'text'})
                self.assertIsNotNone(result)
                self.assertFalse(result.success)

    def test_searches_are_bounded_and_strategy_is_recorded(self):
        query = {'description': 'labels', 'path': '.', 'strategy': 'repository', 'top_k': 5}
        self.assertIsNone(self.guard(self.search, query))
        self.assertEqual(self.searches[-1], query)
        self.assertFalse(self.guard(self.search, {**query, 'path': '..'}).success)
        self.assertFalse(self.guard(self.search, {**query, 'top_k': True}).success)

    def test_protected_mutation_and_replaced_tool_refuse_before_dispatch(self):
        helper = self.root / self.spec['helper_path']
        helper.write_text('tampered', encoding='utf-8')
        self.assertFalse(self.guard(self.read, {'path': self.spec['target']}).success)
        helper.write_text(self.spec['protected'][self.spec['helper_path']], encoding='utf-8')
        self.assertFalse(self.guard(ReadFileTool(), {'path': self.spec['target']}).success)

    def test_wrong_working_directory_and_oversized_arguments_refuse(self):
        self.assertFalse(self.guard(self.write, {'path': self.spec['target'], 'content': 'x' * 20000}).success)
        os.chdir(self.root.parent)
        self.assertFalse(self.guard(self.read, {'path': str(self.root / self.spec['target'])}).success)

    def test_subprocesses_are_exactly_scoped_to_read_only_git_and_owned_checks(self):
        checker = Path('/tmp/fixed-checker.py')
        def allowed(command, cwd=None):
            return allowed_subprocess(command, self.root if cwd is None else cwd,
                                      self.root, 'labels', checker, sys.executable)
        self.assertTrue(allowed([sys.executable, '-B', str(checker), 'labels']))
        self.assertTrue(allowed(['uname', '-p']))
        formatted = [sys.executable, '-I', '-m', 'black', '--quiet', '--workers', '1', '--safe', '--', str(self.root / self.spec['target'])]
        self.assertTrue(allowed(formatted, (self.root / self.spec['target']).parent))
        self.assertTrue(allowed(['git', '--literal-pathspecs', 'rev-parse', '--verify', '--quiet', 'HEAD']))
        self.assertTrue(allowed(['git', '--literal-pathspecs', '-c', 'core.fsmonitor=false', 'ls-files', '-z', '--cached']))
        self.assertTrue(allowed(['git', '-c', 'core.fsmonitor=false', '-C', str(self.root), 'check-ignore', '--no-index', '-q', '--', self.spec['target']]))
        self.assertFalse(allowed(['git', 'status']))
        self.assertFalse(allowed(['uname', '-a']))
        self.assertFalse(allowed(formatted, self.root.parent))
        self.assertFalse(allowed(['git', '--literal-pathspecs', 'config', 'core.hooksPath', '/tmp']))
        self.assertFalse(allowed(['git', '-c', 'core.fsmonitor=false', '-C', str(self.root), 'check-ignore', '--no-index', '-q', '--', '../other']))
        self.assertFalse(allowed([sys.executable, '-B', str(checker), 'invoice']))
        self.assertFalse(allowed([sys.executable, '-B', str(checker), 'labels'], self.root.parent))
