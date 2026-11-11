"""The opt-in codec frames bounded data without activating a runtime."""

import json
import traceback

import pytest

from henchman.cli.headless_protocol import (
    MAX_ANSWER_BYTES,
    MAX_FRAME_BYTES,
    MAX_NESTING,
    MAX_PROMPT_BYTES,
    MAX_SAFE_INTEGER,
    FrameDecoder,
    ProtocolError,
    Request,
    ServerEncoder,
    decode_request,
)


def initialize(**changes):
    value = {"v": 1, "id": 1, "method": "initialize", "params": {
        "session": {"mode": "new"}, "interactive": {"permissions": True, "questions": True},
    }}
    value.update(changes)
    return value


def wire(value):
    return json.dumps(value, ensure_ascii=False).encode() + b"\n"


def test_fragmented_unicode_and_crlf_preserve_literal_input():
    decoder = FrameDecoder()
    run = {"v": 1, "id": 2, "connection_id": "connection", "method": "run", "params": {
        "session_id": "session", "prompt": "中文 😀\n:rocket: [bold]raw[/bold]", "agent": None,
    }}
    frames = wire(initialize()).replace(b"\n", b"\r\n") + wire(run)
    requests = []
    for byte in frames:
        requests.extend(decoder.feed(bytes([byte])))
    decoder.finish()
    assert [item.id for item in requests] == [1, 2]
    assert requests[1].params["prompt"] == run["params"]["prompt"]
    with pytest.raises(TypeError):
        requests[0].params["session"]["mode"] = "resume"


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.0, MAX_SAFE_INTEGER + 1, "1"])
def test_request_ids_are_exact_positive_json_integers(value):
    with pytest.raises(ProtocolError, match="invalid_request"):
        decode_request(wire(initialize(id=value))[:-1])


def test_maximum_exact_request_id_is_supported():
    assert decode_request(wire(initialize(id=MAX_SAFE_INTEGER))[:-1]).id == MAX_SAFE_INTEGER


@pytest.mark.parametrize("value", [True, 0, 2, "1", 1.0])
def test_only_exact_version_one_is_accepted(value):
    with pytest.raises(ProtocolError, match="unsupported_version"):
        decode_request(wire(initialize(v=value))[:-1])


@pytest.mark.parametrize("raw", [
    b'{"v":1,"v":1}', b'{"v":NaN}', b'{"v":Infinity}', b'[]', b'null', b'{} trailing',
    b'\xef\xbb\xbf{}', b'\xff', b'', b'{"v":1,"secret":"\\ud800"}',
])
def test_malformed_frames_are_rejected_without_echo(raw):
    with pytest.raises(ProtocolError) as caught:
        decode_request(raw)
    assert "secret" not in str(caught.value)
    assert "ud800" not in traceback.format_exception(caught.value)[-1]


@pytest.mark.parametrize("change", [
    {"extra": "canary-secret"}, {"method": "exec"}, {"connection_id": "unsolicited"},
    {"params": {"session": {"mode": "current"}, "interactive": {"permissions": True, "questions": True}}},
    {"params": {"session": {"mode": "resume"}, "interactive": {"permissions": True, "questions": True}}},
    {"params": {"session": {"mode": "new", "id": "session"}, "interactive": {"permissions": True, "questions": True}}},
    {"params": {"session": {"mode": "new"}, "interactive": {"permissions": 1, "questions": True}}},
])
def test_unknown_fields_and_implicit_session_choices_fail_closed(change):
    with pytest.raises(ProtocolError) as caught:
        decode_request(wire(initialize(**change))[:-1])
    assert "canary-secret" not in "".join(traceback.format_exception(caught.value))


def test_nesting_limit_precedes_json_recursion_and_ignores_quoted_braces():
    with pytest.raises(ProtocolError, match="nesting_limit"):
        decode_request(b"[" * (MAX_NESTING + 1) + b"0" + b"]" * (MAX_NESTING + 1))
    value = {"v": 1, "id": 2, "connection_id": "connection", "method": "run", "params": {
        "session_id": "session", "prompt": '["\\' * 100, "agent": None,
    }}
    assert decode_request(wire(value)[:-1]).params["prompt"] == value["params"]["prompt"]


def test_oversized_unterminated_frame_retires_decoder_and_releases_buffer():
    decoder = FrameDecoder()
    for _ in range(MAX_FRAME_BYTES // 4096):
        assert decoder.feed(b" " * 4096) == []
    with pytest.raises(ProtocolError, match="frame_limit"):
        decoder.feed(b" ")
    assert decoder.buffered_bytes == 0
    with pytest.raises(ProtocolError, match="decoder_closed"):
        decoder.feed(wire(initialize()))


def test_unterminated_eof_is_not_a_request_and_cannot_be_resumed():
    decoder = FrameDecoder()
    assert decoder.feed(wire(initialize())[:-1]) == []
    with pytest.raises(ProtocolError, match="unterminated_frame"):
        decoder.finish()
    assert decoder.buffered_bytes == 0
    with pytest.raises(ProtocolError, match="decoder_closed"):
        decoder.feed(b"\n")


def test_decoder_bounds_each_input_batch():
    decoder = FrameDecoder()
    with pytest.raises(ProtocolError, match="chunk_limit"):
        decoder.feed(wire(initialize()) * 1000)
    assert decoder.buffered_bytes == 0


def test_raw_answers_are_execution_data_not_repr_or_error_diagnostics():
    value = {"v": 1, "id": 3, "connection_id": "connection", "method": "question.respond", "params": {
        "session_id": "session", "run_id": "run", "decision_id": "question", "generation": 1,
        "answer": " raw-answer-canary\n ",
    }}
    request = decode_request(wire(value)[:-1])
    assert request.params["answer"] == " raw-answer-canary\n "
    assert "raw-answer-canary" not in repr(request)
    value["params"]["unexpected"] = "other-canary"
    with pytest.raises(ProtocolError) as caught:
        decode_request(wire(value)[:-1])
    assert "canary" not in "".join(traceback.format_exception(caught.value))


def test_server_frames_are_literal_single_lines_and_sequence_only_after_encoding():
    encoder = ServerEncoder()
    text = "中文 😀 :rocket: [bold]raw[/bold]\n" * 100
    first = encoder.encode(kind="event", request_id=2, session_id="session", run_id="run",
                           payload={"type": "content", "data": text})
    assert len(first.splitlines()) == 1
    assert json.loads(first) == {"v": 1, "seq": 1, "kind": "event", "request_id": 2,
                               "session_id": "session", "run_id": "run",
                               "payload": {"type": "content", "data": text}}
    with pytest.raises(ProtocolError, match="frame_limit"):
        encoder.encode(kind="event", request_id=2, session_id="session", run_id="run",
                       payload={"data": "x" * MAX_FRAME_BYTES})
    second = encoder.encode(kind="error", request_id=None, session_id=None, run_id=None,
                            payload={"code": "frame_limit"})
    assert json.loads(second)["seq"] == 2


@pytest.mark.parametrize("payload", [float("nan"), float("inf"), {"x": object()}, {1: "bad key"}, "\ud800"])
def test_encoder_rejects_nonportable_json_without_values_in_errors(payload):
    with pytest.raises(ProtocolError):
        ServerEncoder().encode(kind="event", request_id=2, session_id="session", run_id="run", payload=payload)


def test_encoder_does_not_invent_missing_run_or_session_identity():
    with pytest.raises(ProtocolError, match="invalid_envelope"):
        ServerEncoder().encode(kind="event", request_id=1, session_id=None, run_id="run", payload={})


def test_output_validation_stops_at_size_limit_before_traversing_unbounded_tail():
    # The oversized first entry must stop traversal before an unrelated tail.
    with pytest.raises(ProtocolError, match="frame_limit"):
        ServerEncoder().encode(kind="event", request_id=1, session_id="session", run_id="run",
                               payload=["x" * MAX_FRAME_BYTES, object()])


@pytest.mark.parametrize("changes", [
    {"task_verified": True}, {"status": "made_up"}, {"runtime_status": "failed"},
    {"error": {"code": "oops", "message": "failed"}}, {"extra": "not-v1"},
])
def test_result_envelope_cannot_claim_success_without_consistent_runtime_evidence(changes):
    payload = {"status": "completed", "runtime_status": "responded", "task_verified": False, "error": None}
    payload.update(changes)
    with pytest.raises(ProtocolError, match="invalid_result"):
        ServerEncoder().encode(kind="result", request_id=2, session_id="session", run_id="run", payload=payload)


def test_result_encoder_accepts_admitted_completion_and_unadmitted_rejection():
    for run_id, payload in [
        ("operation-run", {"status": "completed", "runtime_status": "responded", "task_verified": False, "error": None}),
        (None, {"status": "rejected", "runtime_status": None, "task_verified": False,
                "error": {"code": "recovery_required", "message": "Resolve existing interrupted work first."}}),
    ]:
        encoded = ServerEncoder().encode(kind="result", request_id=2, session_id="session", run_id=run_id, payload=payload)
        assert json.loads(encoded)["payload"] == payload


def test_server_sequence_exhaustion_never_rounds_or_wraps():
    encoder = ServerEncoder()
    encoder._sequence = MAX_SAFE_INTEGER - 1
    assert json.loads(encoder.encode(kind="response", request_id=1, session_id=None, run_id=None,
                                     payload={}))['seq'] == MAX_SAFE_INTEGER
    with pytest.raises(ProtocolError, match="sequence_exhausted"):
        encoder.encode(kind="response", request_id=1, session_id=None, run_id=None, payload={})


def test_direct_request_construction_validates_and_detaches_original_input():
    params = initialize()["params"]
    item = Request(1, "initialize", None, params)
    params["interactive"]["permissions"] = False
    assert item.params["interactive"]["permissions"] is True
    with pytest.raises(ProtocolError):
        Request(True, "initialize", None, params)


@pytest.mark.parametrize("method,params", [
    ("cancel", {"run_request_id": True, "run_id": None}),
    ("permission.respond", {"session_id": "s", "run_id": "r", "decision_id": "d", "generation": True, "approved": True}),
    ("permission.respond", {"session_id": "s", "run_id": "r", "decision_id": "d", "generation": 1, "approved": 1}),
    ("question.respond", {"session_id": "s", "run_id": "r", "decision_id": "d", "generation": 1, "answer": False}),
    ("run", {"session_id": "s", "prompt": "work", "agent": None, "yes": True}),
])
def test_control_fields_cannot_coerce_truthiness_or_authorize_new_options(method, params):
    with pytest.raises(ProtocolError):
        decode_request(wire({"v": 1, "id": 2, "method": method, "connection_id": "connection", "params": params})[:-1])


def test_parser_exceptions_do_not_retain_raw_document_in_error_chain():
    raw = b'{"v":1,"secret":"raw-diagnostic-canary" BROKEN}'
    with pytest.raises(ProtocolError) as caught:
        decode_request(raw)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert "raw-diagnostic-canary" not in "".join(traceback.format_exception(caught.value))


def test_exact_frame_limit_and_empty_eof_are_supported():
    raw = wire(initialize())[:-1]
    raw += b" " * (MAX_FRAME_BYTES - len(raw)) + b"\n"
    decoder = FrameDecoder()
    found = []
    for start in range(0, len(raw), 4096):
        found.extend(decoder.feed(raw[start:start + 4096]))
    assert len(found) == 1 and found[0].method == "initialize"
    decoder.finish()


def test_malformed_batch_is_atomic_and_decoder_never_recovers_implicitly():
    decoder = FrameDecoder()
    with pytest.raises(ProtocolError):
        decoder.feed(wire(initialize()) + b"not-json\n")
    assert decoder.buffered_bytes == 0
    with pytest.raises(ProtocolError, match="decoder_closed"):
        decoder.finish()


@pytest.mark.parametrize("answer", [None, "", "  exact answer\n"])
def test_question_decline_and_original_answer_are_distinct(answer):
    value = {"session_id": "session", "run_id": "run", "decision_id": "decision", "generation": 1, "answer": answer}
    parsed = decode_request(wire({"v": 1, "id": 3, "method": "question.respond", "connection_id": "connection", "params": value})[:-1])
    assert parsed.params["answer"] == answer


@pytest.mark.parametrize("method,key,limit", [("run", "prompt", MAX_PROMPT_BYTES), ("question.respond", "answer", MAX_ANSWER_BYTES)])
def test_execution_text_bound_is_utf8_bytes_not_characters(method, key, limit):
    params = {"session_id": "session", "prompt": "", "agent": None} if method == "run" else {
        "session_id": "session", "run_id": "run", "decision_id": "decision", "generation": 1, "answer": "",
    }
    params[key] = "😀" * (limit // 4)
    frame = {"v": 1, "id": 2, "method": method, "connection_id": "connection", "params": params}
    assert decode_request(wire(frame)[:-1]).params[key] == params[key]
    params[key] += "x"
    with pytest.raises(ProtocolError, match="frame_limit"):
        decode_request(wire(frame)[:-1])
