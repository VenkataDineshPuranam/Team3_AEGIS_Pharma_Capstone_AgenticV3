"""Unit tests for services/integration/precedent_mint.py (ADR-010) -- Neo4j mocked out,
so these exercise the mint-or-skip decision logic and the finding_hash computation
without a live store."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from packages.domain.payloads import BatchPayload, ReconciliationFinding
from services.integration import precedent_mint


def _batch_payload(findings: tuple[ReconciliationFinding, ...]) -> BatchPayload:
    return BatchPayload(batch_id="B-001", reconciliation_complete=not findings, findings=findings)


def _gap(category="genealogy", status="gap") -> ReconciliationFinding:
    return ReconciliationFinding(category=category, status=status, evidence_ids=(), gap_description="x")


@contextmanager
def _fake_session(mock_session):
    yield mock_session


def test_mint_skips_when_workflow_is_not_batch_review():
    with patch.object(precedent_mint, "session") as mock_session_cm:
        precedent_mint.mint_rejection("R-1", "pv_intake", _batch_payload((_gap(),)), "justification text")
        mock_session_cm.assert_not_called()


def test_mint_skips_when_domain_payload_is_none():
    with patch.object(precedent_mint, "session") as mock_session_cm:
        precedent_mint.mint_rejection("R-1", "batch_review", None, "justification text")
        mock_session_cm.assert_not_called()


def test_mint_skips_when_no_gap_or_conflict_findings():
    """A rejection with only 'complete' findings has nothing precedent-worthy to mint --
    an empty finding_hash would match every other run's retrieve() call indiscriminately,
    exactly what ADR-010 rejects."""
    payload = _batch_payload((ReconciliationFinding(category="genealogy", status="complete", evidence_ids=(), gap_description=None),))
    with patch.object(precedent_mint, "session") as mock_session_cm:
        precedent_mint.mint_rejection("R-1", "batch_review", payload, "justification text")
        mock_session_cm.assert_not_called()


def test_mint_writes_a_merge_for_a_genuine_rejection():
    mock_s = MagicMock()
    payload = _batch_payload((_gap(),))
    with patch.object(precedent_mint, "session", return_value=_fake_session(mock_s)):
        precedent_mint.mint_rejection("R-real-1", "batch_review", payload, "Genealogy gap unresolved.")
    mock_s.run.assert_called_once()
    call_kwargs = mock_s.run.call_args.kwargs
    assert call_kwargs["evidence_id"] == "HP-R-real-1"
    assert call_kwargs["source_file"] == "human_precedent/R-real-1.md"
    assert call_kwargs["finding_categories"] == ["genealogy"]
    assert call_kwargs["justification_excerpt"] == "Genealogy gap unresolved."


def test_mint_never_raises_on_a_store_failure():
    """Best-effort per ADR-010: a Neo4j failure must not propagate -- the human decision
    was already committed to the audit store before this function is even called."""
    payload = _batch_payload((_gap(),))
    with patch.object(precedent_mint, "session", side_effect=RuntimeError("store down")):
        precedent_mint.mint_rejection("R-1", "batch_review", payload, "justification text")  # must not raise


def test_finding_hash_excludes_complete_findings_and_batch_id():
    payload_a = _batch_payload((_gap("genealogy"), ReconciliationFinding(category="lab_results", status="complete", evidence_ids=(), gap_description=None)))
    payload_b = BatchPayload(batch_id="B-999-DIFFERENT", reconciliation_complete=False, findings=(_gap("genealogy"),))
    assert precedent_mint.finding_hash(payload_a.findings) == precedent_mint.finding_hash(payload_b.findings)


def test_finding_hash_differs_for_different_categories():
    a = precedent_mint.finding_hash((_gap("genealogy"),))
    b = precedent_mint.finding_hash((_gap("lab_results"),))
    assert a != b


def test_excerpt_is_truncated():
    mock_s = MagicMock()
    payload = _batch_payload((_gap(),))
    long_text = "x" * 1000
    with patch.object(precedent_mint, "session", return_value=_fake_session(mock_s)):
        precedent_mint.mint_rejection("R-long", "batch_review", payload, long_text)
    assert len(mock_s.run.call_args.kwargs["justification_excerpt"]) == precedent_mint._EXCERPT_MAX_CHARS
