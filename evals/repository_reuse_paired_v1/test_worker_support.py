"""Bound the real retrieval preparation before any provider request."""
from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

import contract as c
import fixtures
from henchman.tools.base import ToolResult
from worker_support import finalize_verification, prepare_retrieval


class PreparationTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_predeclared_query_and_unmodified_result_for_both_arms(self):
        for case in fixtures.CASES:
            for arm, strategy in (('baseline', 'combined'), ('repository', 'repository')):
                with self.subTest(case=case, arm=arm):
                    content = '{"kind":"repository_evidence","complete":true}' if arm == 'repository' else 'ordinary search evidence'
                    structured = {'kind': 'repository_evidence', 'complete': True} if arm == 'repository' else None
                    tool_result = ToolResult(content, success=True, structured_content=structured,
                                             structured_content_present=structured is not None)
                    registry = AsyncMock()
                    registry.execute.return_value = tool_result
                    receipt = await prepare_retrieval(registry, case, arm)
                    args = {'description': fixtures.spec(case)['query'], 'path': '.', 'top_k': 5, 'strategy': strategy}
                    registry.execute.assert_awaited_once_with('pattern_search', args)
                    self.assertEqual(receipt['arguments'], args)
                    self.assertEqual(receipt['content'], content)
                    self.assertEqual(receipt['content_sha256'], hashlib.sha256(content.encode()).hexdigest())
                    self.assertEqual(receipt['structured'], structured)

    async def test_failed_partial_or_oversized_retrieval_cannot_reach_model(self):
        variants = (
            ToolResult('partial', success=False, error='fixture error'),
            ToolResult('{"complete":false}', success=True, structured_content={'kind': 'repository_evidence', 'complete': False}, structured_content_present=True),
            ToolResult('x' * (c.RAW_LIMIT + 1), success=True),
            ToolResult('plain text', success=True),
        )
        for response in variants:
            with self.subTest(response=response.content[:20]):
                registry = AsyncMock()
                registry.execute.return_value = response
                with self.assertRaises(c.Denied):
                    await prepare_retrieval(registry, 'labels', 'repository')

    async def test_unknown_arm_and_fixture_are_refused_before_dispatch(self):
        registry = AsyncMock()
        for case, arm in (('unknown', 'baseline'), ('labels', 'other')):
            with self.assertRaises((c.Denied, ValueError)):
                await prepare_retrieval(registry, case, arm)
        registry.execute.assert_not_awaited()

    async def test_tool_exception_retains_explicit_failure_evidence(self):
        registry = AsyncMock()
        registry.execute.side_effect = OSError('repository unavailable')
        with self.assertRaises(c.Denied) as caught:
            await prepare_retrieval(registry, 'labels', 'repository')
        self.assertEqual(caught.exception.receipt['reason'], 'dispatch_error')
        self.assertEqual(caught.exception.receipt['error_type'], 'OSError')

    async def test_real_bound_registry_returns_actual_fixed_query_evidence(self):
        from henchman.tools.builtins.pattern_search import PatternSearchTool
        from henchman.tools.registry import ToolRegistry

        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as name:
            try:
                for case in fixtures.CASES:
                    root = (Path(name).resolve() / case)
                    spec = fixtures.prepare(root, case)
                    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM='1')
                    commands = (
                        ['git', 'init', '-q'],
                        ['git', 'config', 'user.name', 'Offline Fixture'],
                        ['git', 'config', 'user.email', 'offline@example.invalid'],
                        ['git', 'add', '.'],
                        ['git', '-c', 'commit.gpgsign=false', '-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture'],
                    )
                    for command in commands:
                        subprocess.run(command, cwd=root, env=env, check=True, timeout=15,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    os.chdir(root)
                    registry = ToolRegistry()
                    registry.register(PatternSearchTool(project_root=root))
                    for arm in ('baseline', 'repository'):
                        result = await prepare_retrieval(registry, case, arm)
                        self.assertEqual(result['status'], 'complete')
                        self.assertIn(spec['helper_path'], result['content'])
                        if arm == 'repository':
                            self.assertTrue(result['structured']['complete'])
            finally:
                os.chdir(previous)

    def test_late_stale_changed_or_unavailable_verification_cannot_pass(self):
        from unittest.mock import Mock

        for latest in (
            {'run_id': 'held', 'current_checks_passed': False},
            {'run_id': 'other', 'current_checks_passed': True},
            {'run_id': None, 'current_checks_passed': True},
        ):
            with self.subTest(latest=latest):
                plans = Mock()
                plans.verification_status.return_value = latest
                result = finalize_verification(plans, 'plan', 'held', correlated=True)
                self.assertFalse(result['current'])
        plans = Mock()
        plans.verification_status.side_effect = OSError('unavailable')
        self.assertFalse(finalize_verification(plans, 'plan', 'held', correlated=True)['current'])
        plans.verification_status.side_effect = None
        plans.verification_status.return_value = {'run_id': 'held', 'current_checks_passed': True}
        self.assertFalse(finalize_verification(plans, 'plan', 'held', correlated=False)['current'])
        self.assertTrue(finalize_verification(plans, 'plan', 'held', correlated=True)['current'])
