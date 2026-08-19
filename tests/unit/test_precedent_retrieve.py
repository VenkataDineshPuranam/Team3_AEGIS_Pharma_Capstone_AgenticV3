"""Unit tests for services/integration/precedent_retrieve.py (ADR-010) -- Neo4j mocked
out, exercising the input validation, empty-query short-circuit, and STORE_UNAVAILABLE
error mapping without a live store."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from services.integration import precedent_retrieve
from services.integration.precedent_retrieve import ToolError, retrieve


@contextmanager
def _fake_session(mock_session):
    yield mock_session


def test_retrieve_short_circuits_when_no_categories_or_hash():
    """No finding_categories AND no finding_hash means there is nothing to match against
    -- returning an empty result without hitting the store, rather than running a query
    that (per the Cypher) would match nothing anyway."""
    with patch.object(precedent_retrieve, "session") as mock_session_cm:
        result = retrieve(run_id="R-1", finding_categories=[], finding_hash="", policy_contract_version="v1")
        assert result == {"items": []}
        mock_session_cm.assert_not_called()


def test_retrieve_raises_on_missing_run_id():
    with pytest.raises(ToolError) as exc_info:
        retrieve(run_id="", finding_categories=["genealogy"], finding_hash="", policy_contract_version="v1")
    assert exc_info.value.code == "STORE_UNAVAILABLE"


def test_retrieve_raises_on_missing_policy_version():
    with pytest.raises(ToolError) as exc_info:
        retrieve(run_id="R-1", finding_categories=["genealogy"], finding_hash="", policy_contract_version="")
    assert exc_info.value.code == "STORE_UNAVAILABLE"


def test_retrieve_maps_store_errors_to_store_unavailable():
    with patch.object(precedent_retrieve, "session", side_effect=RuntimeError("connection refused")):
        with pytest.raises(ToolError) as exc_info:
            retrieve(run_id="R-1", finding_categories=["genealogy"], finding_hash="", policy_contract_version="v1")
    assert exc_info.value.code == "STORE_UNAVAILABLE"


def test_retrieve_passes_finding_categories_and_hash_to_the_query():
    mock_s = MagicMock()
    mock_s.run.return_value = []
    with patch.object(precedent_retrieve, "session", return_value=_fake_session(mock_s)):
        retrieve(run_id="R-1", finding_categories=["genealogy", "lab_results"], finding_hash="abc123", policy_contract_version="v1")
    call_kwargs = mock_s.run.call_args.kwargs
    assert call_kwargs["finding_categories"] == ["genealogy", "lab_results"]
    assert call_kwargs["finding_hash"] == "abc123"
    assert call_kwargs["citable_statuses"] == ["approved", "draft"]
