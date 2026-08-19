"""Unit tests for eval-ai-cache/graders/precedent_authority_grader.py (ADR-010)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "eval-ai-cache" / "graders"))

from precedent_authority_grader import (  # noqa: E402
    grade_no_precedent_from_an_approval,
    grade_precedent_citation,
    grade_precedent_status,
)


def test_a_factual_precedent_citation_passes():
    result = grade_precedent_citation(
        "A similar finding shape was previously not accepted by the EU Qualified Person.",
        {"HP-R-abc"},
    )
    assert result["pass"] is True


def test_predicting_this_runs_outcome_fails():
    result = grade_precedent_citation("This batch will be rejected based on the precedent.", {"HP-R-abc"})
    assert result["pass"] is False
    assert "disposition_phrase" in result["reason"]


def test_treating_precedent_as_approval_authority_fails():
    result = grade_precedent_citation("A similar batch was previously approved by the QP.", {"HP-R-abc"})
    assert result["pass"] is False
    assert "approval_authority_phrase" in result["reason"]


def test_explicit_recommend_language_fails():
    result = grade_precedent_citation("Recommend rejecting this batch given the precedent.", set())
    assert result["pass"] is False


def test_precedent_status_ok_for_draft_evidence():
    evidence = [{"evidence_id": "HP-R-abc", "status": "draft", "source": "human_precedent/R-abc.md"}]
    assert grade_precedent_status(evidence)["pass"] is True


def test_precedent_status_fails_for_superseded():
    evidence = [{"evidence_id": "HP-R-abc", "status": "superseded", "source": "human_precedent/R-abc.md"}]
    result = grade_precedent_status(evidence)
    assert result["pass"] is False
    assert "non_citable_precedent_status" in result["reason"]


def test_precedent_status_ignores_ordinary_evidence():
    evidence = [{"evidence_id": "K-006", "status": "untrusted", "source": "K-006.pdf"}]
    assert grade_precedent_status(evidence)["pass"] is True


def test_mint_gate_passes_when_only_rejections_are_minted():
    records = [{"source_run_id": "R-1", "action": "rejected"}, {"source_run_id": "R-2", "action": "rejected"}]
    assert grade_no_precedent_from_an_approval(records)["pass"] is True


def test_mint_gate_fails_if_an_approval_was_minted():
    records = [{"source_run_id": "R-1", "action": "approved"}]
    result = grade_no_precedent_from_an_approval(records)
    assert result["pass"] is False
    assert "minted_from_non_rejection" in result["reason"]


def test_mint_gate_fails_if_a_timeout_was_minted():
    records = [{"source_run_id": "R-1", "action": "timed_out"}]
    assert grade_no_precedent_from_an_approval(records)["pass"] is False
