"""Transport intents cannot manufacture execution authority or settled results."""

import json

import pytest

from henchman.cli.headless_control import HeadlessControl
from henchman.cli.headless_protocol import MAX_SAFE_INTEGER, ProtocolError, decode_request


def request(number, method, params, connection="connection"):
    value = {"v": 1, "id": number, "method": method, "params": dict(params)}
    if method != "initialize":
        value["connection_id"] = connection
    return decode_request(json.dumps(value).encode())


def initialized(*, permissions=True, questions=True):
    state = HeadlessControl()
    state.receive(request(1, "initialize", {
        "session": {"mode": "new"}, "interactive": {"permissions": permissions, "questions": questions},
    }))
    state.bind_session(connection_id="connection", session_id="session")
    return state


def running(**kwargs):
    state = initialized(**kwargs)
    intent = state.receive(request(2, "run", {"session_id": "session", "prompt": "raw-prompt-canary", "agent": None}))
    assert intent.request.params["prompt"] == "raw-prompt-canary"
    assert "raw-prompt-canary" not in repr(intent)
    assert state.run_id is None
    state.admit_run("operation-run")
    return state


def decision_request(number, token, *, answer=" raw-answer-canary\n ", approved=False):
    method = "permission.respond" if token.kind == "permission" else "question.respond"
    params = {"session_id": token.session_id, "run_id": token.run_id, "decision_id": token.id,
              "generation": token.generation}
    params.update({"approved": approved} if token.kind == "permission" else {"answer": answer})
    return request(number, method, params)


def test_session_and_run_ids_are_bound_once_by_embedding_not_client():
    state = initialized()
    with pytest.raises(ProtocolError, match="already_initialized"):
        state.bind_session(connection_id="different", session_id="different")
    with pytest.raises(ProtocolError, match="run_not_reserved"):
        state.admit_run("invented")
    with pytest.raises(ProtocolError, match="session_mismatch"):
        state.receive(request(2, "run", {"session_id": "other", "prompt": "work", "agent": None}))
    state.receive(request(3, "run", {"session_id": "session", "prompt": "work", "agent": "writer"}))
    assert state.run_id is None
    state.admit_run("actual-operation-run")
    with pytest.raises(ProtocolError, match="already_admitted"):
        state.admit_run("replacement")
    assert state.run_id == "actual-operation-run"


def test_no_run_before_handshake_or_second_run_after_reservation():
    state = HeadlessControl()
    with pytest.raises(ProtocolError, match="not_initialized"):
        state.receive(request(1, "run", {"session_id": "session", "prompt": "work", "agent": None}))
    state = running()
    with pytest.raises(ProtocolError, match="run_already_reserved"):
        state.receive(request(3, "run", {"session_id": "session", "prompt": "second", "agent": None}))


def test_duplicate_or_old_request_ids_never_replay_effects():
    state = running()
    cancel = request(3, "cancel", {"run_request_id": 2, "run_id": "operation-run"})
    assert state.receive(cancel).changed is True
    with pytest.raises(ProtocolError, match="request_replayed"):
        state.receive(cancel)
    assert state.receive(request(4, "cancel", cancel.params)).changed is False


@pytest.mark.parametrize("kind", ["permission", "question"])
def test_only_current_bound_decision_can_deliver_original_response(kind):
    state = running()
    token = state.begin_decision("decision", kind)
    wrong = decision_request(3, token)
    value = dict(wrong.params)
    value["run_id"] = "other-run"
    with pytest.raises(ProtocolError, match="stale_decision"):
        state.receive(request(3, wrong.method, value))
    assert state.pending_decision is token
    intent = state.receive(decision_request(4, token))
    assert intent.decision is token
    assert intent.request.params.get("answer") == (" raw-answer-canary\n " if kind == "question" else None)
    assert "raw-answer-canary" not in repr(intent)
    assert state.pending_decision is None
    with pytest.raises(ProtocolError, match="stale_decision"):
        state.receive(decision_request(5, token))


def test_stale_timeout_cannot_retire_new_decision_even_with_reused_label():
    state = running()
    first = state.begin_decision("decision", "question")
    assert state.retire_decision(first) is True
    second = state.begin_decision("decision", "question")
    assert second.generation > first.generation
    assert state.retire_decision(first) is False
    assert state.pending_decision is second
    with pytest.raises(ProtocolError, match="stale_decision"):
        state.receive(decision_request(3, first))


@pytest.mark.parametrize("kind", ["permission", "question"])
def test_unavailable_input_creates_no_waiter_or_implicit_answer(kind):
    state = running(permissions=False, questions=False)
    with pytest.raises(ProtocolError, match="input_unavailable"):
        state.begin_decision("decision", kind)
    assert state.pending_decision is None


def test_cancellation_revokes_decisions_but_does_not_claim_cleanup_or_result():
    state = running()
    token = state.begin_decision("decision", "permission")
    state.receive(request(3, "cancel", {"run_request_id": 2, "run_id": "operation-run"}))
    assert state.cancellation_requested is True
    assert state.result is None
    assert state.pending_decision is None
    with pytest.raises(ProtocolError, match="cancellation_requested"):
        state.begin_decision("new", "question")
    with pytest.raises(ProtocolError, match="stale_decision"):
        state.receive(decision_request(4, token, approved=True))
    # The eventual embedding supplies this only after joining runtime cleanup.
    result = state.claim_result("incomplete")
    assert result.status == "incomplete"
    assert result.run_id == "operation-run" and result.request_id == 2
    with pytest.raises(ProtocolError, match="result_already_claimed"):
        state.claim_result("completed")


def test_cancellation_before_admission_does_not_create_runtime_identity():
    state = initialized()
    state.receive(request(2, "run", {"session_id": "session", "prompt": "work", "agent": None}))
    state.receive(request(3, "cancel", {"run_request_id": 2, "run_id": None}))
    with pytest.raises(ProtocolError, match="cancellation_requested"):
        state.admit_run("late-run")
    assert state.run_id is None
    assert state.claim_result("cancelled").admitted is False


def test_unobserved_run_identity_can_cancel_only_exact_owned_request():
    state = running()
    token = state.begin_decision("decision", "permission")
    with pytest.raises(ProtocolError, match="connection_mismatch"):
        state.receive(request(3, "cancel", {"run_request_id": 2, "run_id": None}, connection="foreign"))
    with pytest.raises(ProtocolError, match="run_mismatch"):
        state.receive(request(4, "cancel", {"run_request_id": 99, "run_id": None}))
    with pytest.raises(ProtocolError, match="run_mismatch"):
        state.receive(request(5, "cancel", {"run_request_id": 2, "run_id": "different-run"}))
    assert state.pending_decision is token and not state.cancellation_requested
    state.receive(request(6, "cancel", {"run_request_id": 2, "run_id": None}))
    assert state.cancellation_requested and state.pending_decision is None
    assert state.run_id == "operation-run" and state.result is None


def test_completed_result_requires_actual_admission_and_no_second_run():
    state = initialized()
    state.receive(request(2, "run", {"session_id": "session", "prompt": "work", "agent": None}))
    with pytest.raises(ProtocolError, match="result_requires_admission"):
        state.claim_result("completed")
    result = state.claim_result("rejected")
    assert result.run_id is None and not result.admitted
    with pytest.raises(ProtocolError, match="run_already_reserved"):
        state.receive(request(3, "run", {"session_id": "session", "prompt": "work", "agent": None}))


@pytest.mark.parametrize("shutdown", [False, True])
def test_disconnect_and_shutdown_retire_waiters_without_asserting_settlement(shutdown):
    state = running()
    token = state.begin_decision("decision", "question")
    if shutdown:
        state.receive(request(3, "shutdown", {}))
    else:
        state.disconnect()
    assert state.closing and state.cancellation_requested and state.result is None
    assert state.pending_decision is None
    with pytest.raises(ProtocolError, match="connection_closing"):
        state.receive(decision_request(4, token))
    assert state.claim_result("cancelled").status == "cancelled"


def test_foreign_connection_cannot_cancel_or_supply_an_answer():
    state = running()
    with pytest.raises(ProtocolError, match="connection_mismatch"):
        state.receive(request(3, "cancel", {"run_request_id": 2, "run_id": "operation-run"}, connection="old"))
    assert not state.cancellation_requested and state.run_id == "operation-run"


def test_wrong_cancel_target_cannot_retire_current_prompt():
    state = running()
    token = state.begin_decision("decision", "permission")
    with pytest.raises(ProtocolError, match="run_mismatch"):
        state.receive(request(3, "cancel", {"run_request_id": 99, "run_id": "operation-run"}))
    assert state.pending_decision is token and not state.cancellation_requested


def test_trusted_binding_failure_has_no_partial_identity_publication():
    state = HeadlessControl()
    with pytest.raises(ProtocolError, match="not_initialized"):
        state.bind_session(connection_id="connection", session_id="session")
    state.receive(request(1, "initialize", {"session": {"mode": "resume", "id": "session"},
                                           "interactive": {"permissions": True, "questions": True}}))
    with pytest.raises(ProtocolError, match="invalid_identity"):
        state.bind_session(connection_id="connection", session_id="bad\nidentity")
    state.bind_session(connection_id="connection", session_id="session")
    state.receive(request(2, "run", {"session_id": "session", "prompt": "work", "agent": None}))
    with pytest.raises(ProtocolError, match="invalid_identity"):
        state.admit_run("bad\nidentity")
    assert state.run_id is None
    state.admit_run("actual")


def test_only_embedding_observation_can_set_raced_terminal_outcome():
    state = running()
    state.receive(request(3, "cancel", {"run_request_id": 2, "run_id": "operation-run"}))
    assert state.result is None
    # Cancellation may lose to already completed execution; the adapter must
    # use its joined runtime outcome, rather than infer it from the request.
    assert state.claim_result("completed").status == "completed"
    with pytest.raises(ProtocolError, match="run_finished"):
        state.receive(request(4, "cancel", {"run_request_id": 2, "run_id": "operation-run"}))


def test_decisions_are_serial_and_generation_has_finite_exact_range():
    state = running()
    state._generation = MAX_SAFE_INTEGER - 1
    token = state.begin_decision("last", "question")
    assert token.generation == MAX_SAFE_INTEGER
    with pytest.raises(ProtocolError, match="decision_pending"):
        state.begin_decision("next", "permission")
    state.retire_decision(token)
    with pytest.raises(ProtocolError, match="sequence_exhausted"):
        state.begin_decision("overflow", "question")


def test_shutdown_before_session_setup_does_not_bind_late_session_or_claim_run():
    state = HeadlessControl()
    state.receive(request(1, "shutdown", {}, connection=None))
    assert state.closing and not state.cancellation_requested and state.result is None
    with pytest.raises(ProtocolError, match="connection_closing"):
        state.bind_session(connection_id="connection", session_id="session")
    with pytest.raises(ProtocolError, match="run_not_reserved"):
        state.claim_result("cancelled")


@pytest.mark.parametrize("status", [True, "invented", "rejected"])
def test_invalid_terminal_claim_does_not_consume_result_slot(status):
    state = running()
    with pytest.raises(ProtocolError, match="invalid_result"):
        state.claim_result(status)
    assert state.result is None
    assert state.claim_result("failed").status == "failed"


def test_explicit_resume_cannot_be_bound_to_a_different_session():
    state = HeadlessControl()
    state.receive(request(1, "initialize", {"session": {"mode": "resume", "id": "requested-session"},
                                           "interactive": {"permissions": False, "questions": False}}))
    with pytest.raises(ProtocolError, match="session_mismatch"):
        state.bind_session(connection_id="connection", session_id="other-session")
    state.bind_session(connection_id="connection", session_id="requested-session")
    state.receive(request(2, "run", {"session_id": "requested-session", "prompt": "new explicit input", "agent": None}))
    assert state.run_id is None and state.result is None
