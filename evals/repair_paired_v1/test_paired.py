"""Offline tests; imports and MockTransport are the only provider path."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import contract
import fixtures


class ContractTests(unittest.TestCase):
    def test_fixed_denominator_and_counterbalanced_order(self):
        rows = contract.plan()["attempts"]
        self.assertEqual(len(rows), 12)
        self.assertEqual(len({r["attempt_id"] for r in rows}), 12)
        for fixture in fixtures.CASES:
            found = [r["arm"] for r in rows if r["fixture"] == fixture]
            self.assertEqual(found, ["direct", "repair", "repair", "direct"])

    def test_no_endpoint_aliases_or_fallback(self):
        for endpoint in (
            "http://localhost:8081/v1",
            "http://127.0.0.1:8082/v1",
            "https://127.0.0.1:8081/v1",
            "http://127.0.0.1:8081/v1/",
            "http://user@127.0.0.1:8081/v1",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(contract.Denied):
                contract.require_target(endpoint, contract.MODEL)
        with self.assertRaises(contract.Denied):
            contract.require_target(contract.ENDPOINT, "other")

    def test_environment_excludes_keys_proxies_and_install(self):
        with (
            tempfile.TemporaryDirectory() as name,
            patch.dict(
                os.environ,
                {"OPENAI_API_KEY": "private", "HTTP_PROXY": "private", "BROWSER": "private"},
            ),
        ):
            env = contract.environment(Path(name), Path("/python"))
            self.assertNotIn("OPENAI_API_KEY", env)
            self.assertNotIn("HTTP_PROXY", env)
            self.assertEqual(env["PIP_NO_INDEX"], "1")
            self.assertEqual(env["UV_OFFLINE"], "1")


class OracleTests(unittest.TestCase):
    def test_mutants_and_weakened_criteria_reject(self):
        for case in fixtures.CASES:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as name:
                root = Path(name)
                spec = fixtures.prepare(root, case)
                (root / spec["target"]).write_text(spec["correct"])
                self.assertTrue(fixtures.oracle(root, case)["numeric_pass"])
                (root / spec["target"]).write_text(spec["constant_mutant"])
                self.assertFalse(fixtures.oracle(root, case)["numeric_pass"])
                (root / spec["target"]).write_text(spec["correct"])
                (root / "criteria.py").write_text('print("pass")\n')
                self.assertFalse(fixtures.oracle(root, case)["accepted"])

    def test_control_requires_identical_bytes(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            spec = fixtures.prepare(root, "already-correct")
            (root / spec["target"]).write_text(spec["correct"] + "\n")
            result = fixtures.oracle(root, "already-correct")
            self.assertTrue(result["numeric_pass"])
            self.assertFalse(result["accepted"])

    def test_target_cannot_execute_imports_or_side_effects(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            fixtures.prepare(root, "addition-repair")
            marker = root / "escaped"
            (root / "target.py").write_text(
                f"open({str(marker)!r},'w').write('bad')\ndef add(a,b): return a+b\n"
            )
            self.assertFalse(fixtures.oracle(root, "addition-repair")["accepted"])
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
