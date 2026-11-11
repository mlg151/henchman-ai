import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import contract
import worker


class WorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_arms_same_input_current_oracle_and_aggregate(self):
        old = Path.cwd()
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            try:
                for arm in ("direct", "repair"):
                    target = root / arm
                    target.mkdir()
                    with patch.dict(
                        os.environ,
                        contract.environment(target / "env", Path(__import__("sys").executable)),
                        clear=True,
                    ):
                        result = await worker.run_attempt(
                            target, "addition-repair", arm, 1, dry=True
                        )
                    if arm == "repair":
                        self.assertEqual(
                            result["repair"]["timeout_seconds"], contract.ATTEMPT_SECONDS
                        )
                    self.assertTrue(result["oracle"]["accepted"], result)
                    self.assertTrue(result["cleanup_joined"], result)
                    self.assertEqual(result["state"], "finished")
                    records = result["budget"]["records"]
                    self.assertTrue(records)
                    self.assertEqual({r["provider"] for r in records}, {"openai_compat"})
                    self.assertEqual({r["model"] for r in records}, {contract.MODEL})
                    self.assertTrue(all(r["agent_id"] for r in records))
                    self.assertEqual(
                        result["budget"]["consumed_requests"],
                        result["transport_usage"]["dispatched_requests"],
                    )
                    self.assertTrue(
                        all(r["run_id"] == result["budget"]["run_id"] for r in result["requests"])
                    )
                a = json.loads((root / "direct" / "worker.json").read_text())
                b = json.loads((root / "repair" / "worker.json").read_text())
                self.assertEqual(a["prompt_sha256"], b["prompt_sha256"])
                self.assertEqual(a["fixture_before"], b["fixture_before"])
            finally:
                os.chdir(old)

    async def test_setup_failure_finalizes_with_no_provider_calls(self):
        old = Path.cwd()
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            try:
                with patch.dict(
                    os.environ,
                    contract.environment(root / "env", Path(__import__("sys").executable)),
                    clear=True,
                ):
                    result = await worker.run_attempt(
                        root, "addition-repair", "direct", 1, dry=True, setup_failure=True
                    )
                self.assertEqual(result["state"], "failed")
                self.assertEqual(result["transport_usage"]["dispatched_requests"], 0)
                self.assertTrue(result["cleanup_joined"])
                self.assertTrue((root / "worker.json").exists())
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()


class ScopeTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_tool_cannot_weaken_protected_criteria(self):
        import httpx
        import fixtures

        old = Path.cwd()
        calls = [
            ("write_file", {"path": "criteria.py", "content": 'print("pass")\n'}),
            (
                "write_file",
                {"path": "target.py", "content": fixtures.spec("addition-repair")["correct"]},
            ),
            None,
        ]

        async def reply(request):
            return httpx.Response(
                200,
                content=worker.synthetic_response(calls.pop(0)),
                headers={"content-type": "text/event-stream"},
            )

        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            try:
                with (
                    patch.dict(
                        os.environ,
                        contract.environment(root / "env", Path(__import__("sys").executable)),
                        clear=True,
                    ),
                    patch.object(worker, "scripted", return_value=httpx.MockTransport(reply)),
                ):
                    result = await worker.run_attempt(
                        root, "addition-repair", "direct", 1, dry=True
                    )
                self.assertTrue(result["oracle"]["criteria_unchanged"])
                self.assertTrue(result["denials"])
                self.assertTrue(result["cleanup_joined"])
                self.assertEqual(
                    (root / "workspace" / "criteria.py").read_bytes(),
                    fixtures.spec("addition-repair")["criteria"].encode(),
                )
            finally:
                os.chdir(old)
