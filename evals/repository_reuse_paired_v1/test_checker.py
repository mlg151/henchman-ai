"""Fixed verifier process exercises the same pure current-byte oracle."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import fixtures


class CheckerTests(unittest.TestCase):
    def invoke(self, root: Path, case: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, '-B', str(Path(__file__).with_name('checker.py')), case],
            cwd=root,
            env={'HOME': str(root), 'USERPROFILE': str(root), 'PATH': os.environ.get('PATH', ''),
                 'SYSTEMROOT': os.environ.get('SYSTEMROOT', ''), 'PYTHONNOUSERSITE': '1'},
            capture_output=True, text=True, timeout=10, check=False,
        )

    def test_correct_protected_fixture_passes_and_mutation_fails(self):
        for case in fixtures.CASES:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as name:
                root = Path(name).resolve()
                spec = fixtures.prepare(root, case)
                (root / spec['target']).write_text(spec['correct'], encoding='utf-8')
                passed = self.invoke(root, case)
                self.assertEqual(passed.returncode, 0, passed.stderr)
                self.assertTrue(json.loads(passed.stdout)['accepted'])
                (root / spec['helper_path']).write_text('def tampered(): pass\n', encoding='utf-8')
                failed = self.invoke(root, case)
                self.assertEqual(failed.returncode, 1, failed.stderr)
                self.assertFalse(json.loads(failed.stdout)['protected_unchanged'])

    def test_unknown_case_refuses(self):
        with tempfile.TemporaryDirectory() as name:
            outcome = self.invoke(Path(name).resolve(), 'unknown')
            self.assertNotEqual(outcome.returncode, 0)


if __name__ == '__main__':
    unittest.main()
