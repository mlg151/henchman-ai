import unittest
import httpcore
import httpx
import contract as c
from local_server import guard, validate_readiness, AuthorityTransport


class LocalTests(unittest.IsolatedAsyncioTestCase):
    def test_idle_and_model_identity_fail_closed(self):
        good = {
            "/health": {"status": "ok"},
            "/v1/models": {"data": [{"id": c.MODEL}]},
            "/slots": [{"is_processing": False}],
        }
        validate_readiness(good)
        for key, value in [
            ("/slots", [{"is_processing": True}]),
            ("/slots", [{}]),
            ("/slots", []),
            ("/v1/models", {"data": [{"id": "other"}]}),
            ("/health", {"status": "loading model"}),
        ]:
            with self.subTest(key=key, value=value), self.assertRaises(c.Denied):
                validate_readiness({**good, key: value})

    async def test_rechecks_at_headers_and_denies_replay(self):
        calls = []
        request = httpx.Request("POST", c.ENDPOINT + "/chat/completions")

        def authorize():
            calls.append(1)

        guard(request, authorize)
        trace = request.extensions["trace"]
        wire = httpcore.Request("POST", c.ENDPOINT + "/chat/completions")
        await trace("http11.send_request_headers.started", {"request": wire})
        self.assertEqual(len(calls), 2)
        with self.assertRaises(c.Denied):
            await trace("http11.send_request_headers.started", {"request": wire})

    async def test_replaced_authority_before_headers_and_extensions_refuse(self):
        changed = False

        def authorize():
            if changed:
                raise c.Denied("changed")

        request = httpx.Request("POST", c.ENDPOINT + "/chat/completions")
        guard(request, authorize)
        changed = True
        with self.assertRaises(c.Denied):
            await request.extensions["trace"](
                "http11.send_request_headers.started",
                {"request": httpcore.Request("POST", str(request.url))},
            )
        with self.assertRaises(c.Denied):
            guard(
                httpx.Request("POST", str(request.url), extensions={"trace": lambda: None}),
                lambda: None,
            )

    async def test_no_readiness_management_or_other_port_effects(self):
        calls = []

        async def reply(request):
            calls.append(request)
            return httpx.Response(200, content=b"{}")

        transport = AuthorityTransport(
            lambda: None, readiness=True, delegate=httpx.MockTransport(reply)
        )
        try:
            for method, path in [
                ("POST", "http://127.0.0.1:8081/slots/0?action=erase"),
                ("GET", "http://127.0.0.1:8082/health"),
                ("GET", "http://127.0.0.1:8081/props"),
            ]:
                with self.assertRaises(c.Denied):
                    await transport.handle_async_request(httpx.Request(method, path))
            self.assertEqual(calls, [])
        finally:
            await transport.aclose()


if __name__ == "__main__":
    unittest.main()


class CommandTests(unittest.TestCase):
    def test_model_file_is_actual_process_model_not_unrelated_file(self):
        from local_server import validate_command

        good = b"llama-server\0--model\0/owned/model.gguf\0--alias\0qwen38-27b-iq3s\0"
        validate_command(good, "/owned/model.gguf")
        for raw, path in [
            (good, "/unrelated/model.gguf"),
            (good.replace(b"qwen38-27b-iq3s", b"other"), "/owned/model.gguf"),
            (good + b"--model-url\0https://external.invalid\0", "/owned/model.gguf"),
        ]:
            with self.assertRaises(c.Denied):
                validate_command(raw, path)


class ActualHttpCoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_connect_time_revocation_prevents_any_http_bytes(self):
        changed = False
        writes = []

        class Wire(httpcore.AsyncNetworkStream):
            async def read(self, max_bytes, timeout=None):
                return b""

            async def write(self, buffer, timeout=None):
                writes.append(buffer)

            async def aclose(self):
                pass

            async def start_tls(self, *args, **kwargs):
                raise AssertionError("no TLS route")

            def get_extra_info(self, info):
                return None

        class Backend(httpcore.AsyncNetworkBackend):
            async def connect_tcp(self, host, port, **kwargs):
                nonlocal changed
                self_target = (host, port)
                self_assert = self_target == ("127.0.0.1", 8081)
                if not self_assert:
                    raise AssertionError(self_target)
                changed = True
                return Wire()

        def authorize():
            if changed:
                raise c.Denied("authority changed during connection")

        native = httpx.AsyncHTTPTransport(retries=0, trust_env=False, http1=True, http2=False)
        native._pool._network_backend = Backend()
        transport = AuthorityTransport(authorize, delegate=native)
        try:
            with self.assertRaises(c.Denied):
                await transport.handle_async_request(
                    httpx.Request("POST", c.ENDPOINT + "/chat/completions", content=b"{}")
                )
            self.assertEqual(writes, [])
        finally:
            await transport.aclose()
