import asyncio
import json
import tempfile
import unittest
from pathlib import Path
import httpx
import contract
from transport import GateTransport, build_provider
from henchman.core.run_budget import RunBudgetLedger, BudgetLimits
from henchman.providers.runtime_budget import RunBudgetScope, use_run_budget
from henchman.providers.base import Message


class GateTests(unittest.IsolatedAsyncioTestCase):
    async def test_sdk_copy_uses_gate_and_exact_role_budget(self):
        seen = []

        async def reply(request):
            seen.append(json.loads(request.content))
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b'data: {"id":"done","object":"chat.completion.chunk","created":1,"model":"qwen38-27b-iq3s","choices":[{"index":0,"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: {"id":"done","object":"chat.completion.chunk","created":1,"model":"qwen38-27b-iq3s","choices":[],"usage":{"prompt_tokens":7,"completion_tokens":2,"total_tokens":9}}\n\ndata: [DONE]\n\n',
            )

        with tempfile.TemporaryDirectory() as name:
            gate = GateTransport(
                alias=contract.MODEL,
                base_url=contract.ENDPOINT,
                authorize=lambda: None,
                delegate=httpx.MockTransport(reply),
                artifacts=Path(name),
            )
            provider = await build_provider(gate)
            ledger = RunBudgetLedger(limits=BudgetLimits(max_requests=12))
            try:
                with use_run_budget(RunBudgetScope(ledger, agent_id="engineer")):
                    chunks = [
                        c
                        async for c in provider.chat_completion_stream(
                            [Message(role="user", content="test")]
                        )
                    ]
                self.assertTrue(chunks)
                self.assertEqual(len(seen), 1)
                self.assertEqual(gate.receipts[0]["run_id"], ledger.run_id)
                self.assertEqual(gate.receipts[0]["agent_id"], "engineer")
                self.assertEqual(ledger.snapshot().consumed_requests, 1)
            finally:
                await provider._client.close()
                await gate.aclose()
            self.assertTrue(
                json.loads((Path(name) / "receipts.json").read_text())["transport_cleanup_joined"]
            )

    async def test_path_model_proxy_redirect_no_fallback(self):
        count = 0

        async def reply(request):
            nonlocal count
            count += 1
            return httpx.Response(307, headers={"location": "https://external.invalid"})

        with tempfile.TemporaryDirectory() as name:
            gate = GateTransport(
                alias=contract.MODEL,
                base_url=contract.ENDPOINT,
                authorize=lambda: None,
                delegate=httpx.MockTransport(reply),
                artifacts=Path(name),
            )
            provider = await build_provider(gate)
            try:
                with use_run_budget(RunBudgetScope(RunBudgetLedger())):
                    with self.assertRaises(Exception):
                        async for _ in provider.chat_completion_stream(
                            [Message(role="user", content="test")]
                        ):
                            pass
                self.assertEqual(count, 1)
                for path in (
                    "http://127.0.0.1:8082/v1/chat/completions",
                    "http://127.0.0.1:8081/v1/models",
                    "https://external.invalid/v1/chat/completions",
                ):
                    with self.assertRaises(contract.Denied):
                        await gate.handle_async_request(httpx.Request("POST", path, content=b"{}"))
                self.assertEqual(count, 1)
            finally:
                await provider._client.close()
                await gate.aclose()


if __name__ == "__main__":
    unittest.main()


class FaultTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_usage_stays_unknown_and_500_never_retries(self):
        from worker import synthetic_response

        for status in (200, 500):
            count = 0

            async def reply(request):
                nonlocal count
                count += 1
                data = synthetic_response(None)
                data = b"\n".join(line for line in data.split(b"\n") if b'"usage"' not in line)
                return httpx.Response(
                    status,
                    content=data if status == 200 else b'{"error":{"message":"scripted failure"}}',
                    headers={
                        "content-type": "text/event-stream" if status == 200 else "application/json"
                    },
                )

            with tempfile.TemporaryDirectory() as name:
                gate = GateTransport(
                    alias=contract.MODEL,
                    base_url=contract.ENDPOINT,
                    authorize=lambda: None,
                    delegate=httpx.MockTransport(reply),
                    artifacts=Path(name),
                )
                provider = await build_provider(gate)
                ledger = RunBudgetLedger()
                try:
                    with use_run_budget(RunBudgetScope(ledger, agent_id="engineer")):
                        try:
                            async for _ in provider.chat_completion_stream(
                                [Message(role="user", content="test")]
                            ):
                                pass
                        except Exception:
                            if status == 200:
                                raise
                    self.assertEqual(count, 1)
                finally:
                    await provider._client.close()
                    await gate.aclose()
                self.assertFalse(
                    gate.usage_summary()["all_dispatched_requests_have_complete_usage"]
                )
                self.assertIsNone(gate.usage_summary()["known_prompt_tokens"])
                self.assertEqual(ledger.snapshot().unknown_dispatched_requests, 1)

    async def test_shared_request_cap_applies_to_different_actors(self):
        from worker import synthetic_response

        calls = []

        async def reply(request):
            calls.append(request)
            return httpx.Response(
                200, content=synthetic_response(None), headers={"content-type": "text/event-stream"}
            )

        with tempfile.TemporaryDirectory() as name:
            gate = GateTransport(
                alias=contract.MODEL,
                base_url=contract.ENDPOINT,
                authorize=lambda: None,
                delegate=httpx.MockTransport(reply),
                artifacts=Path(name),
            )
            provider = await build_provider(gate)
            ledger = RunBudgetLedger(limits=BudgetLimits(max_requests=2))
            try:
                for actor in ("engineer", "child"):
                    with use_run_budget(RunBudgetScope(ledger, agent_id=actor)):
                        async for _ in provider.chat_completion_stream(
                            [Message(role="user", content="test")]
                        ):
                            pass
                with use_run_budget(RunBudgetScope(ledger, agent_id="child")):
                    with self.assertRaises(Exception):
                        async for _ in provider.chat_completion_stream(
                            [Message(role="user", content="third")]
                        ):
                            pass
                self.assertEqual(len(calls), 2)
                self.assertEqual(
                    {r.agent_id for r in ledger.snapshot().records}, {"engineer", "child"}
                )
            finally:
                await provider._client.close()
                await gate.aclose()

    async def test_output_and_input_override_refuse_before_delegate(self):
        count = 0

        async def reply(request):
            nonlocal count
            count += 1
            raise AssertionError("not reached")

        with tempfile.TemporaryDirectory() as name:
            gate = GateTransport(
                alias=contract.MODEL,
                base_url=contract.ENDPOINT,
                authorize=lambda: None,
                delegate=httpx.MockTransport(reply),
                artifacts=Path(name),
            )
            provider = await build_provider(gate)
            try:
                for content, options in [("test", {"max_tokens": 8192}), ("word " * 50000, {})]:
                    with use_run_budget(RunBudgetScope(RunBudgetLedger())):
                        with self.assertRaises(Exception):
                            async for _ in provider.chat_completion_stream(
                                [Message(role="user", content=content)], **options
                            ):
                                pass
                self.assertEqual(count, 0)
            finally:
                await provider._client.close()
                await gate.aclose()

    async def test_cancelled_stream_joins_pull_and_close_preserving_reason(self):
        started = asyncio.Event()
        closed = asyncio.Event()

        class Stream(httpx.AsyncByteStream):
            async def __aiter__(self):
                started.set()
                await asyncio.Event().wait()
                yield b"unreachable"

            async def aclose(self):
                closed.set()

        async def reply(request):
            return httpx.Response(
                200, stream=Stream(), headers={"content-type": "text/event-stream"}
            )

        with tempfile.TemporaryDirectory() as name:
            gate = GateTransport(
                alias=contract.MODEL,
                base_url=contract.ENDPOINT,
                authorize=lambda: None,
                delegate=httpx.MockTransport(reply),
                artifacts=Path(name),
            )
            provider = await build_provider(gate)

            async def run():
                with use_run_budget(RunBudgetScope(RunBudgetLedger())):
                    async for _ in provider.chat_completion_stream(
                        [Message(role="user", content="test")]
                    ):
                        pass

            task = asyncio.create_task(run())
            await started.wait()
            task.cancel("original paired cancellation")
            with self.assertRaises(asyncio.CancelledError) as caught:
                await task
            self.assertEqual(str(caught.exception), "original paired cancellation")
            await provider._client.close()
            await gate.aclose()
            self.assertTrue(closed.is_set())
            self.assertTrue(gate._ownership_settled)
