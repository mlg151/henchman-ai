"""Operation evidence must never imply that an uncertain effect is safe to replay."""

import copy
import hashlib
from concurrent.futures import ThreadPoolExecutor

import pytest

from henchman.core.operation_recovery import (
    DispatchPermit,
    OperationContext,
    OperationJournal,
    OperationRecoveryError,
    OperationResult,
)
from henchman.utils.evidence_redaction import EvidenceRedactor

CONTEXT = OperationContext("project", "session", "run", "turn", "engineer", "call")
DIGEST = hashlib.sha256(b"never persist executable arguments").hexdigest()


def queue(journal: OperationJournal, operation_id: str = "op", *, effect: str = "effectful") -> None:
    journal.queue(CONTEXT, tool_name="shell", effect=effect, input_digest=DIGEST,
                  operation_id=operation_id)


def test_one_dispatch_per_attempt_and_idempotent_result() -> None:
    journal = OperationJournal("project", "session")
    queue(journal)
    queue(journal)
    with ThreadPoolExecutor(max_workers=8) as pool:
        permits = list(pool.map(lambda _: journal.start("op"), range(16)))
    assert sum(permit is not None for permit in permits) == 1
    permit = next(permit for permit in permits if permit is not None)
    result = OperationResult("done", True)
    first = journal.finish(permit, result)
    assert journal.finish(permit, result) == first
    assert journal.start("op") is None
    with pytest.raises(OperationRecoveryError, match="conflicting_result"):
        journal.finish(permit, OperationResult("different", True))
    with pytest.raises(OperationRecoveryError, match="invalid_permit"):
        journal.finish(DispatchPermit("op", "forged"), result)


def test_duplicate_identity_cannot_change_inputs_or_session() -> None:
    journal = OperationJournal("project", "session")
    queue(journal)
    with pytest.raises(OperationRecoveryError, match="conflicting_operation"):
        journal.queue(CONTEXT, tool_name="shell", effect="effectful",
                      input_digest="f" * 64, operation_id="op")
    with pytest.raises(OperationRecoveryError, match="session_mismatch"):
        queue(OperationJournal("project", "another"))


def test_cancel_before_start_is_known_but_after_start_is_unknown() -> None:
    journal = OperationJournal("project", "session")
    queue(journal, "queued")
    assert journal.cancel("queued").state == "cancelled"
    assert journal.start("queued") is None
    queue(journal)
    permit = journal.start("op")
    assert permit is not None
    assert journal.cancel("op").state == "outcome_unknown"
    assert journal.report().blocking_operation_ids == ("op",)
    assert journal.finish(permit, OperationResult("late observed result", True)).state == "completed"
    assert not journal.report().blocking_operation_ids


def test_restart_blocks_effects_but_allows_read_only_reconciliation() -> None:
    journal = OperationJournal("project", "session", owner_id="original")
    queue(journal)
    permit = journal.start("op")
    assert permit is not None
    restored = OperationJournal.from_state(journal.export_state(), owner_id="restored")
    queue(restored, "second")
    # Even callers which forget the explicit recovery step cannot start effects.
    with pytest.raises(OperationRecoveryError, match="unresolved_operation"):
        restored.start("second")
    assert restored.recover().records[0].state == "outcome_unknown"
    queue(restored, "inspect", effect="read")
    assert restored.start("inspect") is not None
    assert restored.start("op") is None
    assert restored.finish(permit, OperationResult("correlated late result", True)).state == "completed"
    assert restored.start("second") is not None


def test_same_process_restoration_does_not_adopt_an_old_dispatch_owner() -> None:
    journal = OperationJournal("project", "session")
    queue(journal)
    journal.start("op")
    restored = OperationJournal.from_state(journal.export_state())
    assert restored.recover().records[0].state == "outcome_unknown"
    assert restored.report().blocking_operation_ids == ("op",)


def test_resolution_is_revision_checked_and_does_not_invent_completion() -> None:
    journal = OperationJournal("project", "session")
    queue(journal)
    journal.start("op")
    unknown = journal.cancel("op")
    with pytest.raises(OperationRecoveryError, match="stale_revision"):
        journal.resolve("op", expected_revision=unknown.revision - 1,
                        decision="abandon", note="I accept the uncertain effect")
    resolved = journal.resolve("op", expected_revision=unknown.revision,
                               decision="abandon", note="User inspected external state")
    assert resolved.state == "outcome_unknown" and resolved.resolution == "abandoned"
    assert not journal.report().blocking_operation_ids


def test_retry_requires_runtime_single_use_authority_and_new_attempt() -> None:
    journal = OperationJournal("project", "session")
    queue(journal)
    journal.start("op")
    unknown = journal.cancel("op")
    authorization = journal.authorize_retry("op", expected_revision=unknown.revision)
    restored = OperationJournal.from_state(journal.export_state())
    with pytest.raises(OperationRecoveryError, match="invalid_retry_authorization"):
        restored.retry(authorization, operation_id="retry", note="explicit user retry")
    retried = journal.retry(authorization, operation_id="retry", note="explicit user retry")
    assert retried.retry_of == "op" and retried.state == "queued"
    assert journal.report().records[0].state == "outcome_unknown"
    assert journal.report().records[0].resolution == "retried"
    assert journal.start("retry") is not None
    with pytest.raises(OperationRecoveryError, match="invalid_retry_authorization"):
        journal.retry(authorization, operation_id="another", note="same token")


def test_concurrent_resolution_invalidates_retry_authority() -> None:
    journal = OperationJournal("project", "session")
    queue(journal)
    permit = journal.start("op")
    assert permit is not None
    unknown = journal.cancel("op")
    authorization = journal.authorize_retry("op", expected_revision=unknown.revision)
    journal.finish(permit, OperationResult("completed meanwhile", True))
    with pytest.raises(OperationRecoveryError, match="stale_revision"):
        journal.retry(authorization, operation_id="retry", note="now stale")
    assert len(journal.report().records) == 1


def test_evidence_redacted_on_write_and_projection_without_altering_identities() -> None:
    policy = EvidenceRedactor(["credential-value", "op"])
    journal = OperationJournal("project", "session", redactor=policy)
    journal.queue(CONTEXT, tool_name="shell", effect="effectful", input_digest=DIGEST,
                  operation_id="op", description="credential-value")
    permit = journal.start("op")
    assert permit is not None
    journal.finish(permit, OperationResult("credential-value later-secret", False, "credential-value"))
    policy.register_secret("later-secret")
    state = journal.export_state()
    assert "credential-value" not in str(state) and "later-secret" not in str(state)
    record = journal.report().records[0]
    assert record.operation_id == "op" and record.context == CONTEXT
    assert record.result == OperationResult("[REDACTED] [REDACTED]", False, "[REDACTED]")


@pytest.mark.parametrize("damage", ["version", "duplicate", "missing_claim", "unexpected", "bad_state"])
def test_state_codec_rejects_corruption(damage: str) -> None:
    journal = OperationJournal("project", "session")
    queue(journal)
    journal.start("op")
    state = copy.deepcopy(journal.export_state())
    if damage == "version":
        state["version"] = 2
    elif damage == "duplicate":
        state["operations"].append(copy.deepcopy(state["operations"][0]))
    elif damage == "missing_claim":
        state["operations"][0]["claim_hash"] = None
    elif damage == "unexpected":
        state["argv"] = ["do not persist this"]
    else:
        state["operations"][0]["record"]["state"] = "running"
    with pytest.raises(OperationRecoveryError, match="invalid_state"):
        OperationJournal.from_state(state)


@pytest.mark.parametrize("damage", ["definition", "self_reference", "missing_retry", "two_retries", "resolution_state"])
def test_state_codec_rejects_invalid_retry_history(damage: str) -> None:
    journal = OperationJournal("project", "session")
    queue(journal)
    journal.start("op")
    unknown = journal.cancel("op")
    token = journal.authorize_retry("op", expected_revision=unknown.revision)
    journal.retry(token, operation_id="retry", note="Explicit user retry")
    state = journal.export_state()
    record = state["operations"][1]["record"]
    if damage == "definition":
        record["input_digest"] = "f" * 64
    elif damage == "self_reference":
        record["retry_of"] = "retry"
    elif damage == "missing_retry":
        state["operations"].pop()
    elif damage == "two_retries":
        duplicate = copy.deepcopy(state["operations"][1])
        duplicate["record"]["operation_id"] = "another"
        state["operations"].append(duplicate)
    else:
        state["operations"][0]["record"]["resolution"] = "verified"
        record["retry_of"] = None
    with pytest.raises(OperationRecoveryError, match="invalid_state"):
        OperationJournal.from_state(state)
