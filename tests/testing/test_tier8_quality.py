"""Tier 8 quality infrastructure tests."""

from __future__ import annotations

from pathlib import Path

from henchman.testing.contract import ContractSuite
from henchman.testing.vcr import CassetteInteraction, CassetteLibrary


def test_cassette_library_round_trips_interactions(tmp_path: Path) -> None:
    """Cassette storage should persist and load recorded interactions."""
    library = CassetteLibrary(base_dir=tmp_path / "cassettes")
    interactions = [
        CassetteInteraction(
            method="GET",
            url="/v1/health",
            request_body={"check": "health"},
            response_status=200,
            response_body={"status": "ok"},
        )
    ]

    saved_path = library.save("health-check", interactions)
    loaded = library.load("health-check")

    assert saved_path.exists()
    assert loaded[0].response_body["status"] == "ok"
    assert library.match("health-check", method="GET", url="/v1/health") is not None


def test_contract_suite_validates_required_shape() -> None:
    """Contract validation should report missing keys and type mismatches."""
    suite = ContractSuite()

    ok_errors = suite.validate(
        {"session_id": "abc", "status": "active"},
        {"session_id": str, "status": str},
    )
    bad_errors = suite.validate(
        {"status": 3},
        {"session_id": str, "status": str},
    )

    assert ok_errors == []
    assert "Missing required field: session_id" in bad_errors
    assert "Field status expected str, got int" in bad_errors
