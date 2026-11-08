"""Read-only interpreter contracts; never exec candidate programs."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import fixtures

class OracleTests(unittest.TestCase):
    def check(self, case, text=None, mutate=None):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name).resolve();spec=fixtures.prepare(root,case)
            (root/spec['target']).write_text(text if text is not None else spec['correct'])
            if mutate: mutate(root,spec)
            return fixtures.oracle(root,case)

    def test_three_distinct_correct_callers_pass_and_stub_fails(self):
        self.assertEqual(len(fixtures.CASES),3)
        for case in fixtures.CASES:
            with self.subTest(case=case):
                result=self.check(case);self.assertTrue(result['accepted'],result)
                self.assertTrue(result['helper_calls_pass']);self.assertGreater(result['examples'],3)
                self.assertFalse(self.check(case,fixtures.spec(case)['initial'])['accepted'])

    def test_semantically_equivalent_copy_fails_actual_helper_reuse(self):
        for case in fixtures.CASES:
            with self.subTest(case=case):
                result=self.check(case,fixtures.spec(case)['copied'])
                self.assertFalse(result['accepted']);self.assertFalse(result['helper_calls_pass'])

    def test_correct_output_with_mutated_caller_input_is_rejected(self):
        text = fixtures.spec('labels')['correct'].replace(
            '    return result\n', '    values.append("unexpected")\n    return result\n')
        result = self.check('labels', text)
        self.assertFalse(result['accepted'], result)

    def test_rebinding_an_argument_does_not_mutate_its_caller(self):
        text = fixtures.spec('labels')['correct'].replace(
            '    result = []\n', '    original = values\n    values = []\n    result = []\n').replace(
            '    for value in values:\n', '    for value in original:\n')
        result = self.check('labels', text)
        self.assertTrue(result['accepted'], result)

    def test_empty_set_constructor_supports_helper_reuse_without_shadow_bypass(self):
        text = fixtures.spec('labels')['correct'].replace(
            '    result = []\n', '    seen = set()\n    result = []\n',
        ).replace(
            '        if label and label not in result:\n',
            '        if label and label not in seen:\n            seen.add(label)\n',
        )
        result = self.check('labels', text)
        self.assertTrue(result['accepted'], result)
        self.assertFalse(self.check('labels', text.replace('set()', 'set(values)'))['accepted'])
        helper_alias = fixtures.spec('labels')['correct'].replace(
            'from shared import normalization',
            'from shared.normalization import normalize_label as set',
        ).replace('normalization.normalize_label(value)', 'set(value)')
        self.assertTrue(self.check('labels', helper_alias)['accepted'])
        for replacement in ('    set = []\n    seen = set()\n',
                            '    seen = set()\n    set = []\n'):
            with self.subTest(replacement=replacement):
                shadowed = text.replace('    seen = set()\n', replacement)
                self.assertFalse(self.check('labels', shadowed)['accepted'])

    def test_mutation_during_iteration_is_not_evaluated_as_a_snapshot(self):
        text = fixtures.spec('labels')['correct'].replace(
            '    result = []\n', '    saved = ""\n    if values:\n        saved = values[1]\n    result = []\n',
        ).replace(
            '        label = normalization.normalize_label(value)\n',
            '        if value == "one":\n            values[1] = "tampered"\n        label = normalization.normalize_label(value)\n',
        ).replace(
            '    return result\n', '    if values:\n        values[1] = saved\n    return result\n',
        )
        result = self.check('labels', text)
        self.assertFalse(result['accepted'], result)

    def test_protected_helper_tests_and_instruction_bytes_cannot_change(self):
        for case in fixtures.CASES:
            for path in fixtures.spec(case)['protected']:
                with self.subTest(case=case,path=path):
                    result=self.check(case,mutate=lambda root,spec:(root/path).write_text('weakened'))
                    self.assertFalse(result['accepted']);self.assertFalse(result['protected_unchanged'])

    def test_malicious_or_nonterminating_programs_are_not_executed(self):
        bad=[
          'import os\ndef unique_labels(values):\n    return os.system("touch /tmp/should-never-exist")\n',
          'open("/tmp/should-never-exist", "w")\ndef unique_labels(values): return []\n',
          'def unique_labels(values):\n    while True: pass\n',
          'def unique_labels(values):\n    return unique_labels(values)\n',
          'def unique_labels(values):\n    return [0] * 1000000000\n',
          'def unique_labels(values):\n    return values.__class__.__mro__\n',
          'def unique_labels(values):\n    return __import__("socket").socket()\n',
          '@print("bad")\ndef unique_labels(values): return []\n',
        ]
        for text in bad:
            with self.subTest(text=text):
                result=self.check('labels',text);self.assertFalse(result['accepted'])
                self.assertTrue(result.get('reason'))

    def test_executable_annotations_cannot_be_silently_ignored(self):
        text = fixtures.spec('labels')['correct'].replace(
            'def unique_labels(values):',
            'def unique_labels(values: trigger()) -> trigger():',
        )
        result = self.check('labels', text)
        self.assertFalse(result['accepted'], result)

    def test_oracle_is_current_and_link_refusal_is_explicit(self):
        def linked(root,spec):
            original=root/spec['target'];copy=root/'copy';original.rename(copy)
            try:
                original.symlink_to(copy)
            except (OSError,NotImplementedError):
                self.skipTest('Symlink creation is unavailable')
        result=self.check('labels',mutate=linked)
        self.assertFalse(result['accepted']);self.assertIn('invalid',result['reason'])

    def test_oversized_target_is_refused_before_reading_its_content(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name).resolve()
            spec = fixtures.prepare(root, 'labels')
            target = root / spec['target']
            target.write_bytes(b'x' * 8193)
            original = Path.read_bytes
            def guarded(path):
                if path == target:
                    raise AssertionError('oversized target was read')
                return original(path)
            with patch.object(Path, 'read_bytes', guarded):
                result = fixtures.oracle(root, 'labels')
            self.assertFalse(result['accepted'])
            self.assertIn('invalid', result['reason'])
