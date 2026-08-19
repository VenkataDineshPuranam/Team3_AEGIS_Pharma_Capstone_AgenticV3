"""Stage 21 gap-closure -- INJ-066: a newly registered tool requesting write access and
silently changing a disposition. See services/integration/tool_manifest.py.
"""
import json

import pytest

from services.integration.tool_manifest import ToolManifestViolation, load_manifest, verify_manifest


def test_current_tool_contracts_match_the_recorded_manifest():
    results = verify_manifest()
    assert all(r["status"] == "ok" for r in results)
    assert len(results) == 9  # every real tool contract in packages/contracts/tool_contracts/ (ADR-010: +precedent.retrieve)


def test_no_tool_across_any_workflow_can_write_formulation_specification_or_clinical_parameters():
    """Stage 21 gap-closure -- INJ-006: executives prohibit any AI from autonomously
    changing formulation, specification, or clinical parameters. Verified directly, across
    every registered tool in every one of the six workflows (batch_review, pv_intake,
    supply_planning, research_review, clinical_integrity, regulatory_completeness) -- not
    asserted for one workflow and assumed for the rest."""
    results = verify_manifest()
    assert len(results) == 9
    assert all(r["status"] == "ok" for r in results)
    manifest = load_manifest()
    assert all(tool["read_only"] is True for tool in manifest["tools"]), (
        "every registered tool must be read_only -- a write-capable tool anywhere would be "
        "the exact prohibited-optimization risk this inject describes"
    )


def test_an_unregistered_tool_is_rejected(tmp_path, monkeypatch):
    """The INJ-066 scenario itself: a newly-registered tool that was never reviewed
    through this manifest."""
    import services.integration.tool_manifest as tm

    fake_contracts_dir = tmp_path / "tool_contracts"
    fake_contracts_dir.mkdir()
    (fake_contracts_dir / "batch_reconcile.schema.json").write_text(
        (tm.CONTRACTS_DIR / "batch_reconcile.schema.json").read_text()
    )
    # The attack: a new tool contract appears that the manifest never recorded.
    (fake_contracts_dir / "batch_status_write.schema.json").write_text(
        json.dumps({"read_only": True, "owning_context": "Batch Review"})
    )
    monkeypatch.setattr(tm, "CONTRACTS_DIR", fake_contracts_dir)

    with pytest.raises(ToolManifestViolation, match="unregistered"):
        verify_manifest()


def test_a_write_capability_escalation_is_rejected(tmp_path, monkeypatch):
    """The manifest catches a registered tool's own read_only flag flipping to False,
    which is exactly the 'silently changes a disposition' half of INJ-066."""
    import services.integration.tool_manifest as tm

    fake_contracts_dir = tmp_path / "tool_contracts"
    fake_contracts_dir.mkdir()
    original = json.loads((tm.CONTRACTS_DIR / "batch_reconcile.schema.json").read_text())
    original["read_only"] = False  # tampered
    (fake_contracts_dir / "batch_reconcile.schema.json").write_text(json.dumps(original))

    fake_manifest = tmp_path / "tool_manifest.json"
    real_manifest = tm.load_manifest()
    fake_manifest.write_text(json.dumps(real_manifest))

    monkeypatch.setattr(tm, "CONTRACTS_DIR", fake_contracts_dir)
    monkeypatch.setattr(tm, "MANIFEST_PATH", fake_manifest)

    # The hash changed (read_only flipped), so this is caught as a hash mismatch --
    # a tampered contract cannot silently pass as unchanged.
    with pytest.raises(ToolManifestViolation, match="hash mismatch|no longer present"):
        verify_manifest()
