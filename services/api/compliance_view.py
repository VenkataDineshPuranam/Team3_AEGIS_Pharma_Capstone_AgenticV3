"""Compliance evidence read model -- Stage 25 (Super Admin only).

Assembles the EU AI Act risk classification, ISO/IEC 42001 control mapping, and open-gap
register for display, by parsing the pipe tables straight out of the real governance docs
(docs/governance/compliance/*.md) at request time -- the same "read from the artefact, never
hand-copy it" rule governance_view.py already follows for policy/HITL/evidence data. If the
docs are updated, this endpoint reflects it on the next request with no code change.

This is deliberately NOT a "we are compliant" claim -- both source docs say so explicitly
("reasoned classification, not a legal determination"). This module reports that framing
verbatim rather than smoothing it into marketing language.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPLIANCE_DIR = REPO_ROOT / "docs" / "governance" / "compliance"


class ComplianceDocsUnavailable(Exception):
    pass


def _parse_pipe_table(markdown: str) -> list[dict[str, str]]:
    """Parses the first pipe-table in a markdown string into a list of row dicts keyed by
    header cell, stripping markdown bold/emphasis markers for plain display text."""
    lines = [ln for ln in markdown.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 2:
        return []
    header = [c.strip() for c in lines[0].strip("|").split("|")]
    rows = []
    for line in lines[2:]:  # skip header + separator row
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != len(header):
            continue
        cleaned = [re.sub(r"\*\*|~~", "", c) for c in cells]
        rows.append(dict(zip(header, cleaned, strict=True)))
    return rows


def _read(name: str) -> str:
    path = COMPLIANCE_DIR / name
    if not path.exists():
        raise ComplianceDocsUnavailable(f"{path} does not exist.")
    return path.read_text()


def snapshot() -> dict:
    try:
        eu_ai_act = _read("eu_ai_act_risk_classification.md")
        iso42001 = _read("iso42001_control_mapping.md")
        gaps = _read("gap_assessment.md")
    except ComplianceDocsUnavailable as exc:
        raise ComplianceDocsUnavailable(str(exc)) from exc

    return {
        "eu_ai_act": {
            "status": "Reasoned classification, not a legal determination.",
            "source": "docs/governance/compliance/eu_ai_act_risk_classification.md",
            "boundary_pack_questions": _parse_pipe_table(eu_ai_act),
        },
        "iso42001": {
            "status": "Every clause maps to a real artifact or a registered, owned gap.",
            "source": "docs/governance/compliance/iso42001_control_mapping.md",
            "clause_mapping": _parse_pipe_table(iso42001),
        },
        "gap_register": {
            "source": "docs/governance/compliance/gap_assessment.md",
            "gaps": _parse_pipe_table(gaps),
        },
    }
