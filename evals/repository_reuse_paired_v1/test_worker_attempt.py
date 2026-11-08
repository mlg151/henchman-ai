"""An owned dry worker must actually retrieve, edit and verify the fixture."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

import contract as c
import launch
import worker


class AttemptTests(unittest.TestCase):
    def test_existing_workspace_is_refused_without_overwriting_its_files(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve()
            target = root / 'workspace' / 'app' / 'labels.py'
            target.parent.mkdir(parents=True)
            target.write_text('pre-existing content', encoding='utf-8')
            with self.assertRaises(c.Denied):
                worker.prepare_workspace(root, 'labels')
            self.assertEqual(target.read_text(encoding='utf-8'), 'pre-existing content')

    def test_dry_baseline_uses_actual_retrieval_and_preserves_oracle(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve() / 'attempt'
            row = {'attempt_id': 'labels-1-baseline', 'fixture': 'labels',
                   'arm': 'baseline', 'repeat': 1}
            outcome = launch.run_one(root, row, dry=True, attempt_seconds=90)
            self.assertTrue(outcome['cleanup']['joined'], outcome)
            self.assertTrue(outcome['finalized_after_owned_cleanup'])
            self.assertEqual(outcome['state'], 'finished', outcome)
            self.assertTrue(outcome['accepted'], outcome)
            worker = outcome['worker']
            self.assertEqual(worker['retrieval']['arguments']['strategy'], 'combined')
            self.assertEqual(worker['retrieval']['status'], 'complete')
            self.assertTrue(worker['oracle']['accepted'])
            self.assertTrue(worker['oracle']['protected_unchanged'])
            self.assertTrue(worker['oracle']['helper_calls_pass'])
            self.assertEqual(worker['denials'], [])
            self.assertEqual(worker['tool_failures'], [])
            self.assertTrue(worker['verification_current'])
            self.assertTrue(worker['transport_usage']['all_dispatched_requests_have_complete_usage'])
            self.assertTrue(all(row['response_bytes'] > 0 and row['usage_source'] == 'synthetic-scripted-SSE-usage'
                                for row in worker['requests']))

    def test_correct_artifact_without_current_correlated_verification_is_incomplete(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve() / 'attempt'
            row = {'attempt_id': 'labels-1-baseline', 'fixture': 'labels',
                   'arm': 'baseline', 'repeat': 1}
            script = ("import json,pathlib,sys; pathlib.Path(sys.argv[1]).write_text(json.dumps("
                      "{'state':'finished','cleanup_joined':True,'oracle':{'accepted':True},"
                      "'denials':[],'verification_current':False}))")
            result = launch.run_one(root, row, dry=True,
                                    command=[sys.executable, '-c', script, str(root / 'worker.json')],
                                    attempt_seconds=10)
            self.assertTrue(result['cleanup']['joined'])
            self.assertEqual(result['state'], 'finished')
            self.assertFalse(result['accepted'])

    def test_denied_effect_cannot_be_hidden_by_correct_artifact_and_current_check(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve() / 'attempt'
            row = {'attempt_id': 'labels-1-baseline', 'fixture': 'labels',
                   'arm': 'baseline', 'repeat': 1}
            script = ("import json,pathlib,sys; pathlib.Path(sys.argv[1]).write_text(json.dumps("
                      "{'state':'finished','cleanup_joined':True,'oracle':{'accepted':True},"
                      "'denials':[{'kind':'network'}],'verification_current':True}))")
            result = launch.run_one(root, row, dry=True,
                                    command=[sys.executable, '-c', script, str(root / 'worker.json')],
                                    attempt_seconds=10)
            self.assertTrue(result['cleanup']['joined'])
            self.assertEqual(result['state'], 'finished')
            self.assertFalse(result['accepted'])
