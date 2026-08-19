"""Validates services/integration/precedent_retrieve.py's real output against the actual
packages/contracts/tool_contracts/precedent_retrieve.schema.json (ADR-010) -- proving the
implementation matches the contract, not re-deriving it (BC-10).

Requires a live Neo4j -- skipped otherwise, same BLOCKED_BY_ENVIRONMENT convention as
test_evidence_retrieve_contract.py.
"""
import json
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from jsonschema import validate

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "packages" / "contracts" / "tool_contracts" / "precedent_retrieve.schema.json"

pytestmark = pytest.mark.skipif(
    not os.environ.get("NEO4J_PASSWORD") or "xxxxxxxx" in os.environ.get("NEO4J_URI", ""),
    reason="BLOCKED_BY_ENVIRONMENT: Neo4j not configured",
)


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text())


def test_schema_declares_read_only_and_batch_review_scope(schema):
    assert schema["read_only"] is True
    assert schema["owning_context"] == "Batch Review"
    assert schema["input"]["additionalProperties"] is False
    assert schema["output"]["additionalProperties"] is False


def test_retrieve_output_matches_schema_on_empty_match(schema):
    """Uses a category that cannot exist in ReconciliationFinding's closed category enum
    (packages/domain/payloads.py) and an unmatchable hash -- guaranteed no overlap
    regardless of how many real precedents other tests have minted into the live store."""
    from services.integration.precedent_retrieve import retrieve

    result = retrieve(
        run_id="R-contract-precedent-empty",
        finding_categories=["nonexistent_test_category_xyz"],
        finding_hash="no-such-hash",
        policy_contract_version="v1",
    )
    validate(instance=result, schema=schema["output"])
    assert result["items"] == []


def test_retrieve_never_returns_non_citable_status(schema):
    """The schema's own output enum only allows approved/draft -- proves the live query
    respects it, matching evidence_retrieve's own equivalent test."""
    from services.integration.precedent_retrieve import retrieve

    result = retrieve(
        run_id="R-contract-precedent-status",
        finding_categories=["genealogy", "lab_results", "deviations"],
        finding_hash="",
        policy_contract_version="v1",
    )
    for item in result["items"]:
        assert item["status"] in ("approved", "draft")


def test_retrieve_after_mint_finds_the_precedent(schema):
    """End-to-end against the real store: mint a rejection, then retrieve it by
    overlapping finding_categories."""
    from packages.domain.payloads import BatchPayload, ReconciliationFinding
    from services.integration.precedent_mint import mint_rejection
    from services.integration.precedent_retrieve import retrieve

    run_id = "R-contract-precedent-roundtrip"
    payload = BatchPayload(
        batch_id="B-CONTRACT",
        reconciliation_complete=False,
        findings=(
            ReconciliationFinding(category="genealogy", status="gap", evidence_ids=(), gap_description="test gap"),
        ),
    )
    mint_rejection(run_id, "batch_review", payload, "Genealogy packet incomplete for lot.")

    result = retrieve(
        run_id="R-contract-precedent-roundtrip-reader",
        finding_categories=["genealogy"],
        finding_hash="",
        policy_contract_version="v1",
    )
    validate(instance=result, schema=schema["output"])
    ids = {item["evidence_id"] for item in result["items"]}
    assert f"HP-{run_id}" in ids
