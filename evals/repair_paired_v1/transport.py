"""Bounded raw SDK evidence; adapted from reviewed v6 without its model launcher."""

from __future__ import annotations
import asyncio
import hashlib
import json
import os
import time
from pathlib import Path
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any
import httpx
from contract import (
    Denied as QualificationDenied,
    RAW_LIMIT,
    OUTPUT as OUTPUT_TOKENS,
    REQUESTS as REQUESTS_PER_CASE,
    ATTEMPT_SECONDS as CASE_SECONDS,
    KEY as LOCAL_KEY,
    MODEL,
    INPUT,
    require_target,
    settings_data,
)


def serial(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return serial(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): serial(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def write_json(path: Path, value: Any) -> None:
    """Private evidence, for a caller-owned fresh artifact directory only."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = json.dumps(serial(value), indent=2, sort_keys=True).encode() + b"\n"
    with path.open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(data)


async def joined_close(task):
    """Finish an owned close even when its caller is cancelled repeatedly."""
    cancellation = None
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as exc:
            cancellation = cancellation or exc
        except BaseException:
            break
    if cancellation is not None:
        if not task.cancelled():
            task.exception()  # The close records its own failure before returning.
        raise cancellation
    return task.result()


class UsageStream(httpx.AsyncByteStream):
    """Tee exact response bytes and derive per-request provider-reported usage."""

    def __init__(self, source, receipt, artifact):
        self.source, self.receipt, self.artifact = source, receipt, artifact
        self.raw = bytearray()
        self.pending = bytearray()
        self.sha = hashlib.sha256()
        self.saw_done = False
        self._iterator = None
        self._close_task = None
        self._finalized = False
        self._pull_task = None
        self._iteration_claimed = False

    def __aiter__(self):
        if self._iteration_claimed or self._close_task is not None:
            raise QualificationDenied("Qualification response is single-consumer")
        self._iteration_claimed = True
        self._iterator = self._iterate()
        return self

    async def __anext__(self):
        if self._close_task is not None:
            raise StopAsyncIteration
        if self._iterator is None:
            raise QualificationDenied("Qualification response iteration was not claimed")
        if self._pull_task is not None and not self._pull_task.done():
            raise QualificationDenied("Qualification response has an active reader")
        self._pull_task = asyncio.create_task(anext(self._iterator))
        return await self._pull_task

    async def _iterate(self):
        primary = None
        try:
            async for chunk in self.source:
                self.sha.update(chunk)
                self.receipt["response_bytes"] += len(chunk)
                self.raw.extend(chunk[: max(0, RAW_LIMIT - len(self.raw))])
                if self.receipt["response_bytes"] > RAW_LIMIT:
                    raise QualificationDenied("Response stream exceeds qualification byte bound")
                self.pending.extend(chunk)
                if len(self.pending) > RAW_LIMIT:
                    raise QualificationDenied("SSE record exceeds qualification bound")
                while b"\n" in self.pending:
                    line, _, rest = self.pending.partition(b"\n")
                    self.pending = bytearray(rest)
                    self._line(bytes(line).rstrip(b"\r"))
                yield chunk
            if self.pending:
                self._line(bytes(self.pending))
            self.receipt["transport_eof"] = True
        except GeneratorExit as exc:
            primary = exc
            self.receipt["stream_close_type"] = "GeneratorExit"
            if not self.saw_done:
                self.receipt["stream_error_type"] = "GeneratorExit"
            raise
        except BaseException as exc:
            primary = exc
            self.receipt["stream_error_type"] = type(exc).__name__
            raise
        finally:
            try:
                self._finalize()
            except BaseException as exc:
                self.receipt["stream_evidence_error_type"] = type(exc).__name__
                if primary is None:
                    raise

    def _finalize(self):
        if self._finalized:
            return
        # OpenAI SDK can stop consuming after [DONE] before transport EOF. Final
        # observations are derived from bytes already delivered, never invented.
        self.receipt["stream_complete"] = self.saw_done
        self.receipt["response_sha256"] = self.sha.hexdigest()
        self.receipt["raw_omitted_bytes"] = self.receipt["response_bytes"] - len(self.raw)
        with self.artifact.open("xb") as stream:
            os.chmod(self.artifact, 0o600)
            stream.write(self.raw)
        self.receipt["usage_complete"] = bool(self.receipt["usage"] is not None and self.saw_done)
        self._finalized = True

    def _line(self, line):
        if not line.startswith(b"data:"):
            return
        data = line[5:].strip()
        if data == b"[DONE]":
            self.saw_done = True
            return
        try:
            payload = json.loads(data)
        except (ValueError, UnicodeDecodeError):
            self.receipt["invalid_sse_json"] = True
            return
        if isinstance(payload, dict) and isinstance(payload.get("id"), str):
            self.receipt["provider_response_id"] = payload["id"][:256]
        usage = payload.get("usage") if isinstance(payload, dict) else None
        if isinstance(usage, dict):
            fields = (usage.get("prompt_tokens"), usage.get("completion_tokens"))
            if all(type(number) is int and number >= 0 for number in fields):
                self.receipt["usage"] = usage
                self.receipt["usage_source"] = "local-server-reported-SSE-usage"
                if fields[1] > OUTPUT_TOKENS:
                    self.receipt["output_cap_violation"] = True
                    raise QualificationDenied("Server reported output beyond requested cap")

    async def aclose(self):
        if self._close_task is None:
            self._close_task = asyncio.create_task(self._close())
        await joined_close(self._close_task)

    async def _close(self):
        error = None
        # Own each pull separately from its SDK consumer. A cancelled read is
        # joined before raw observations can be finalized or the source closed.
        if self._pull_task is not None:
            if not self._pull_task.done():
                self._pull_task.cancel("qualification stream closing")
            await asyncio.gather(self._pull_task, return_exceptions=True)
        for close in (
            self.source.aclose,
            self._iterator.aclose if self._iterator is not None else None,
        ):
            if close is not None:
                try:
                    await close()
                except BaseException as exc:
                    error = error or exc
        try:
            self._finalize()
        except BaseException as exc:
            error = error or exc
        self.receipt["stream_cleanup_joined"] = error is None
        if error is not None:
            self.receipt["stream_cleanup_error_type"] = type(error).__name__
            raise error


class GateTransport(httpx.AsyncBaseTransport):
    """No automatic transport: explicit injected delegate only, including in tests."""

    def __init__(
        self,
        *,
        alias: str,
        delegate,
        artifacts: Path,
        base_url: str,
        authorize,
        request_cap=REQUESTS_PER_CASE,
    ):
        require_target(base_url, alias)
        if not callable(authorize):
            raise QualificationDenied("Explicit dispatch authority required")
        self.base_url, self.authorize = base_url, authorize
        self.alias, self.delegate, self.artifacts = alias, delegate, artifacts
        self.request_cap = request_cap
        self.receipts: list[dict[str, Any]] = []
        self.denials: list[str] = []
        self.closed = False
        self._streams = []
        self._dispatches = set()
        self._close_task = None
        self._ownership_settled = False
        self._cleanup_error_type = None
        artifacts.mkdir(parents=True, exist_ok=True, mode=0o700)

    async def handle_async_request(self, request):
        if self.closed:
            raise QualificationDenied("Qualification transport is closed")
        try:
            if request.method != "POST" or str(request.url) != self.base_url + "/chat/completions":
                raise QualificationDenied("Provider endpoint/method is outside the qualification")
            if len(request.content) > RAW_LIMIT:
                raise QualificationDenied("Request body exceeds qualification bound")
            body = json.loads(request.content)
            if (
                body.get("model") != self.alias
                or body.get("stream") is not True
                or body.get("temperature") != 0
                or "reasoning_effort" in body
                or body.get("max_tokens") != OUTPUT_TOKENS
                or "max_completion_tokens" in body
                or body.get("stream_options") != {"include_usage": True}
            ):
                raise QualificationDenied("Provider request escaped frozen model/settings bounds")
            from henchman.providers.request_budget import estimate_serialized_input

            input_payload = {
                key: body[key]
                for key in (
                    "messages",
                    "tools",
                    "response_format",
                    "tool_choice",
                    "functions",
                    "function_call",
                )
                if key in body
            }
            if estimate_serialized_input(input_payload, model=MODEL) > INPUT:
                raise QualificationDenied("Serialized input exceeds frozen approximate budget")
            if set(body) - {
                "model",
                "messages",
                "tools",
                "tool_choice",
                "temperature",
                "max_tokens",
                "stream",
                "stream_options",
            }:
                raise QualificationDenied("Unreviewed wire options")
            scope = __import__(
                "henchman.providers.runtime_budget", fromlist=["current_run_budget"]
            ).current_run_budget()
            if scope is None:
                raise QualificationDenied("Missing task aggregate accounting")
            if request.headers.get("authorization") != "Bearer " + LOCAL_KEY:
                raise QualificationDenied("Unexpected credential at local qualification transport")
            if len(self.receipts) >= self.request_cap:
                raise QualificationDenied("Per-case provider request bound reached")
        except (ValueError, QualificationDenied) as exc:
            self.denials.append(type(exc).__name__ + ": " + str(exc))
            raise
        index = len(self.receipts) + 1
        receipt = {
            "request_index": index,
            "run_id": scope.ledger.run_id,
            "agent_id": scope.agent_id,
            "url": str(request.url),
            "model": body["model"],
            "request_sha256": hashlib.sha256(request.content).hexdigest(),
            "request_bytes": len(request.content),
            "max_output_tokens": OUTPUT_TOKENS,
            "request_started_monotonic": time.monotonic(),
            "http_status": None,
            "response_bytes": 0,
            "usage": None,
            "usage_source": None,
            "stream_complete": False,
            "usage_complete": False,
            "transport_eof": False,
            "dispatch_settled": False,
            "dispatch_started": False,
            "effective_http_timeouts": dict(request.extensions.get("timeout", {})),
        }
        self.receipts.append(receipt)  # Admission before await; concurrent requests share the cap.
        try:
            (self.artifacts / f"request-{index:03d}.json").write_bytes(request.content)
            os.chmod(self.artifacts / f"request-{index:03d}.json", 0o600)
        except BaseException as exc:
            receipt["dispatch_settled"] = True
            receipt["dispatch_error_type"] = type(exc).__name__
            raise

        async def dispatch():
            try:
                self.authorize()
                receipt["dispatch_started"] = True
                response = await self.delegate.handle_async_request(request)
                receipt["http_status"] = response.status_code
                receipt["response_headers_after_ms"] = (
                    time.monotonic() - receipt["request_started_monotonic"]
                ) * 1000
                response.stream = UsageStream(
                    response.stream,
                    receipt,
                    self.artifacts / f"response-{index:03d}.sse",
                )
                self._streams.append(response.stream)
                if self.closed or 300 <= response.status_code < 400:
                    await response.aclose()
                    raise QualificationDenied("Response arrived after close or redirected")
                return response
            except BaseException as exc:
                receipt["dispatch_error_type"] = type(exc).__name__
                receipt["dispatch_error_after_ms"] = (
                    time.monotonic() - receipt["request_started_monotonic"]
                ) * 1000
                raise
            finally:
                receipt["dispatch_settled"] = True

        task = asyncio.create_task(dispatch())
        self._dispatches.add(task)

        def settled(done):
            if not receipt["dispatch_settled"]:
                receipt["dispatch_settled"] = True
                receipt["dispatch_error_type"] = (
                    "CancelledError" if done.cancelled() else "unstarted_dispatch"
                )
            self._dispatches.discard(done)

        task.add_done_callback(settled)
        return await task

    def flush_receipts(self):
        final = self._close_task is not None and self._close_task.done() and self._ownership_settled
        path = self.artifacts / ("receipts.json" if final else "receipts-before-close.json")
        if not path.exists():
            write_json(
                path,
                {
                    "requests": self.receipts,
                    "denials": self.denials,
                    "usage": self.usage_summary(),
                    "finalized": final,
                    "transport_cleanup_joined": final and self._cleanup_error_type is None,
                    "transport_cleanup_error_type": self._cleanup_error_type,
                },
            )

    async def aclose(self):
        if self._close_task is None:
            self.closed = True
            self._close_task = asyncio.create_task(self._close())
        primary = None
        try:
            await joined_close(self._close_task)
        except BaseException as exc:
            primary = exc
        try:
            self.flush_receipts()
        except BaseException:
            if primary is None:
                raise
        if primary is not None:
            raise primary

    async def _close(self):
        # No new admissions can occur. Even a delegate that suppresses cancellation
        # must settle before its late response enters the final stream close set.
        pending = list(self._dispatches)
        for task in pending:
            task.cancel("qualification transport closing")
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        error = None
        for close in [stream.aclose for stream in self._streams] + [self.delegate.aclose]:
            try:
                await close()
            except BaseException as exc:
                error = error or exc
        self._ownership_settled = True
        self._cleanup_error_type = type(error).__name__ if error is not None else None
        if error is not None:
            raise error

    def usage_summary(self):
        dispatched = [row for row in self.receipts if row["dispatch_started"]]
        known = [row["usage"] for row in dispatched if row["usage"] is not None]
        return {
            "admitted_requests": len(self.receipts),
            "dispatched_requests": len(dispatched),
            "usage_reported_requests": len(known),
            "usage_complete_requests": sum(row["usage_complete"] for row in dispatched),
            "all_dispatched_requests_have_complete_usage": bool(dispatched)
            and all(row["usage_complete"] for row in dispatched),
            "known_prompt_tokens": sum(item["prompt_tokens"] for item in known) if known else None,
            "known_completion_tokens": sum(item["completion_tokens"] for item in known)
            if known
            else None,
            "scope": "All requests observed by this transport; missing usage remains unknown",
            "cost": {
                "amount_usd": 0,
                "source": "local-only-route-no-hosted-billing; hardware cost unmeasured",
            },
        }


async def build_provider(gate: GateTransport):
    """Construct SDK with injected gate; never selects a provider or endpoint fallback."""
    from openai import AsyncOpenAI
    from importlib.metadata import version

    if version("openai") != "2.21.0":
        raise QualificationDenied("Unqualified OpenAI SDK profile; expected 2.21.0")

    from henchman.providers.factory import create_configured_provider

    from henchman.config.schema import Settings

    settings = Settings.model_validate(settings_data())
    provider = create_configured_provider(settings.providers)
    await provider._client.close()  # Constructor allocates a client, makes no requests.
    provider._client = AsyncOpenAI(
        api_key=LOCAL_KEY,
        base_url=gate.base_url,
        max_retries=0,
        http_client=httpx.AsyncClient(
            transport=gate,
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(CASE_SECONDS, connect=5, pool=5),
        ),
    )
    provider._qualification_transport = gate
    return provider
