"""prompt_guard -- PI/PG (Prompt Injection detection / Prompt Guarding), Stage 23.

WHAT THIS IS, AND JUST AS IMPORTANTLY WHAT IT IS NOT
----------------------------------------------------
ADR-004 establishes three independent structural layers that make a prohibited action
unrepresentable: layer 1 (schema absence -- `extra="forbid"` on every payload model),
layer 2 (tool capability absence -- no tool contract exposes a disposition field), and
layer 3 (the runtime `prohibited_action_guard`). That ADR explicitly REJECTED "runtime
guard only" with the reasoning "a guard is a single point of failure."

This module does not reopen that decision. It adds two *bracketing* layers around the
existing three, neither of which is ever the only thing standing between an attacker and
a governance failure:

  layer 0  scan_input()   -- runs on UNTRUSTED text BEFORE it reaches a model prompt.
  layer 4  scan_output()  -- runs on GENERATED text AFTER the model responds.

The distinction that matters: layers 1-3 make a bad *outcome* structurally impossible.
Layers 0 and 4 make a bad *attempt* visible and recordable. A pattern matcher can always
be evaded by a paraphrase, so this module is designed to answer "was an attack attempted,
and is there a record of it?" -- not "are we safe?". Anything that treats a `clear`
verdict here as a safety guarantee has misread this docstring.

Threat basis: security/threat-models/threat_catalogue.md T-01 (indirect prompt injection
via a downstream free-text field), which tests/security/test_prompt_injection_red_team.py
already exercises live against B-EVIL. That test asserts the STRUCTURAL control catches
the attack regardless of model compliance; this module is what makes the same attack
*visible at the boundary* instead of only being caught three layers later.

Deterministic by construction: every verdict here comes from pattern matching over text.
This module never asks a model whether a prompt is an attack, for the same reason
hooks.md forbids the guard asking a model to judge its own output -- a compromised model
is exactly the thing being defended against.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Literal

from packages.domain.state import ProhibitionContract

# Bumped whenever a pattern is added, removed, or changed. Recorded in the AI SBOM
# (security/sbom/ai_sbom.json) so a guard-ruleset change is a visible supply-chain event
# rather than a silent one -- security/sbom/verify_ai_sbom.py fails if this drifts from
# what the SBOM records.
PROMPT_GUARD_VERSION = "1.0.0"

Verdict = Literal["clear", "flagged", "blocked"]
Severity = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class PatternHit:
    pattern_id: str
    category: str
    severity: Severity
    #: The matched span, truncated. Recorded so an operator can see WHAT matched without
    #: the full untrusted text being copied into logs or an audit record.
    excerpt: str


@dataclass(frozen=True)
class InputScan:
    """Result of scanning untrusted text destined for a prompt.

    `verdict` is advisory to the caller, which decides what to do:
      clear    -- no known-attack pattern matched.
      flagged  -- something matched at low/medium severity. Callers generally proceed
                  WITH the text neutralized (see `neutralized`), and record the hit.
      blocked  -- a high-severity pattern matched. Callers should refuse rather than
                  send. Refusing is always safe here: this is decision *support*, so
                  declining to answer costs a convenience, never a safety outcome.
    """

    verdict: Verdict
    hits: tuple[PatternHit, ...] = ()
    #: The input with matched instruction-like spans defanged, safe to embed in a prompt.
    #: Always populated, even when the verdict is `clear` (in which case it equals the
    #: input) -- so a caller cannot accidentally use the raw text by forgetting a branch.
    neutralized: str = ""
    #: Stable fingerprint of the ORIGINAL text. Lets an audit record point at the exact
    #: input that was scanned without storing attacker-controlled content verbatim.
    input_sha256: str = ""

    @property
    def blocked(self) -> bool:
        return self.verdict == "blocked"


@dataclass(frozen=True)
class OutputScan:
    """Result of scanning generated text before it reaches a human.

    Separate from `prohibited_action_guard.check` rather than merged into it: that guard
    enforces ADR-004's per-workflow prohibition contract on a `DecisionSupportOutput` and
    is load-bearing for the graph's routing. This one runs over free-form assistant text
    (the record chatbot) where there is no DecisionSupportOutput to check, and adds two
    checks that guard has no reason to make -- system-prompt leakage and citation
    fabrication. Where their concerns overlap (banned disposition terms), this delegates
    to the same ProhibitionContract, so there is one source of truth for what is banned.
    """

    verdict: Verdict
    hits: tuple[PatternHit, ...] = ()
    #: Citations the model emitted that do not exist in the allowed set. A non-empty
    #: value is always `blocked` -- a fabricated evidence id is the single failure mode
    #: this whole system's provenance requirement exists to prevent.
    fabricated_citations: tuple[str, ...] = ()
    matched_banned_terms: tuple[str, ...] = field(default=())

    @property
    def blocked(self) -> bool:
        return self.verdict == "blocked"


# --- pattern registry -------------------------------------------------------------
#
# Each entry: (id, category, severity, compiled regex).
#
# Severity means "what should the caller do", not "how clever was the attack":
#   high   -- the text is trying to replace the operator's instructions or exfiltrate
#             them. There is no legitimate reason for a batch finding or an operator's
#             question about a record to contain this. Refuse.
#   medium -- attack-shaped but with plausible innocent readings. Neutralize and record.
#   low    -- worth recording for pattern-of-abuse analysis; not worth refusing over.

_INPUT_PATTERNS: tuple[tuple[str, str, Severity, re.Pattern[str]], ...] = (
    # --- instruction override -----------------------------------------------------
    (
        "PI-001", "instruction_override", "high",
        re.compile(
            r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}?"
            r"\b(all|any|the|your|previous|prior|above|earlier|preceding|system)\b"
            r"[^.\n]{0,40}?\b(instruction|instructions|prompt|prompts|rule|rules|"
            r"direction|directions|guideline|guidelines|constraint|constraints)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PI-002", "instruction_override", "high",
        re.compile(r"\b(new|updated|revised)\s+(system\s+)?(prompt|instructions?)\s*[:=]", re.IGNORECASE),
    ),
    # --- role / persona hijack ----------------------------------------------------
    (
        "PI-003", "role_hijack", "high",
        re.compile(
            r"\byou\s+are\s+(now|no\s+longer)\b|"
            r"\b(act|behave|respond)\s+as\s+(if\s+you\s+are\s+)?(an?\s+)?"
            r"(unrestricted|uncensored|different|new)\b|"
            r"\b(developer|god|admin|debug)\s+mode\b|\bDAN\s+mode\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PI-004", "role_hijack", "medium",
        # Chat-role smuggling: a free-text field trying to open a new turn.
        re.compile(r"^\s*(system|assistant|developer)\s*:", re.IGNORECASE | re.MULTILINE),
    ),
    # --- system-prompt exfiltration ------------------------------------------------
    (
        "PI-005", "exfiltration", "high",
        re.compile(
            r"\b(repeat|print|reveal|show|output|echo|disclose|reproduce|summarize)\b"
            r"[^.\n]{0,40}?\b(system\s+prompt|your\s+instructions|your\s+prompt|"
            r"initial\s+instructions|the\s+prompt\s+above|everything\s+above)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PI-006", "exfiltration", "medium",
        re.compile(r"\b(api[_\s-]?key|secret|credential|password|bearer\s+token)\b", re.IGNORECASE),
    ),
    # --- control-token / delimiter smuggling ---------------------------------------
    (
        "PI-007", "delimiter_smuggling", "high",
        re.compile(
            r"<\|(im_start|im_end|endoftext|system|eot_id|start_header_id)\|>|"
            r"\[/?INST\]|<<\s*SYS\s*>>|\[/?SYSTEM\]",
            re.IGNORECASE,
        ),
    ),
    (
        "PI-008", "delimiter_smuggling", "medium",
        # Fenced block claiming to be a system/instruction channel.
        re.compile(r"```\s*(system|instructions?|prompt)\b", re.IGNORECASE),
    ),
    # --- output-format hijack ------------------------------------------------------
    (
        "PI-009", "output_hijack", "medium",
        re.compile(
            r"\b(respond|reply|answer|output)\b[^.\n]{0,25}?\bonly\s+with\b|"
            r"\b(say|write|output)\s+exactly\b|\bverbatim\b",
            re.IGNORECASE,
        ),
    ),
    # --- governance-specific: coercing a terminal decision --------------------------
    #
    # The V1/V2 non-negotiable is that no agent makes a terminal safety/release/
    # allocation decision. Text ASKING for one is not itself a policy violation (a
    # confused operator may genuinely ask "should I release this?"), which is why this is
    # medium, not high -- the answer is constrained by the system prompt and by
    # scan_output, and a legitimate question deserves an explanation rather than a
    # refusal. It is recorded because a burst of these is a meaningful signal.
    (
        "PI-010", "decision_coercion", "medium",
        re.compile(
            r"\b(should\s+i|can\s+i|do\s+i|tell\s+me\s+(whether|if)|just\s+tell\s+me)\b"
            r"[^.\n]{0,60}?\b(release|reject|approve|recall|reprocess|relabel|allocate|"
            r"reserve|ship|report(?:able)?|unblind)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PI-011", "decision_coercion", "medium",
        re.compile(
            r"\b(as\s+(the|an?)\s+)?(qualified\s+person|qp|medical\s+monitor|regulator|"
            r"auditor|inspector)\b[^.\n]{0,30}?\bi\s+(authorize|approve|instruct|order)\b",
            re.IGNORECASE,
        ),
    ),
    # --- obfuscation ---------------------------------------------------------------
    (
        "PI-012", "obfuscation", "low",
        # Long base64-ish runs: a common wrapper for an injection payload. Low severity
        # because evidence ids, hashes, and trace ids legitimately look like this.
        re.compile(r"[A-Za-z0-9+/]{80,}={0,2}"),
    ),
    (
        "PI-013", "obfuscation", "medium",
        # Zero-width and bidi control characters -- no legitimate use in a pharma record
        # field, and a known way to hide instruction text from a human reviewer.
        re.compile(r"[​-‏‪-‮⁠-⁤﻿]"),
    ),
)

# Fragments of THIS system's own operator instructions. If generated text contains one,
# the model is echoing its instructions back out -- the success condition for PI-005.
_SYSTEM_PROMPT_MARKERS: tuple[str, ...] = (
    "your only job is to",
    "respond with only a json object",
    "belongs exclusively to a human",
    "do not fabricate evidence_ids",
    "you are the critic/verifier",
    "decision-support agent for",
)

_OUTPUT_PATTERNS: tuple[tuple[str, str, Severity, re.Pattern[str]], ...] = (
    (
        "PG-001", "instruction_compliance", "high",
        # The model announcing it has taken on an injected instruction.
        re.compile(
            r"\b(as\s+(instructed|requested|per\s+the\s+instruction)\s+(in|by)\s+the\s+"
            r"(finding|record|field|note|comment)|ignoring\s+my\s+(previous\s+)?instructions)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "PG-002", "role_abandonment", "high",
        re.compile(r"\b(i\s+am\s+now|i\s+will\s+now\s+act\s+as|switching\s+to)\b[^.\n]{0,30}\bmode\b", re.IGNORECASE),
    ),
    (
        "PG-003", "unauthorized_authority", "high",
        # Claiming to make, or to have made, the decision that belongs to a human.
        re.compile(
            r"\bi\s+(hereby\s+)?(approve|authorize|release|reject|recall|allocate|certify)\b|"
            r"\b(my|this)\s+(decision|determination|authorization)\s+is\b",
            re.IGNORECASE,
        ),
    ),
)


def _truncate(text: str, limit: int = 80) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[:limit] + "…"


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _worst(hits: tuple[PatternHit, ...]) -> Verdict:
    if any(h.severity == "high" for h in hits):
        return "blocked"
    return "flagged" if hits else "clear"


#: Categories whose matched spans get defanged before the text is embedded in a prompt.
#: `decision_coercion` is deliberately absent -- an operator asking "should I release
#: this?" is a legitimate question that deserves an explanation of who actually decides,
#: and mangling their words would make the answer incoherent. The system prompt and
#: scan_output are what keep that answer inside the guardrails, not redaction of the
#: question. `obfuscation` is absent too: its control-character half is stripped wholesale
#: below, and its base64 half is a reporting signal, not something to rewrite.
_NEUTRALIZE_CATEGORIES = frozenset(
    {"instruction_override", "role_hijack", "exfiltration", "delimiter_smuggling", "output_hijack"}
)

_CONTROL_CHARS = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")


def _neutralize(text: str, hits: tuple[PatternHit, ...]) -> str:
    """Defang instruction-shaped spans so the text can still be summarized without the
    model reading it as an instruction.

    The replacement names the PATTERN, never the matched text. Echoing the payload back
    inside a `[NEUTRALIZED: ...]` wrapper would leave the instruction sitting in the
    prompt verbatim, which is most of what the attacker wanted -- models do not reliably
    treat a bracketed label as a reason to stop reading. The attempt is not lost: the
    matched excerpt travels in the `PatternHit` instead, which is what gets shown to the
    human and recorded, so the person investigating still sees exactly what was in the
    field while the model never does.

    Neutralization is a rewrite rather than deletion of the whole field: the surrounding
    legitimate content (a real deviation description with an injection appended) stays
    summarizable. Control characters are the exception -- they are stripped outright,
    because their entire purpose is to be invisible.
    """
    if not hits:
        return text
    cleaned = _CONTROL_CHARS.sub("", text)
    for pid, category, _sev, pattern in _INPUT_PATTERNS:
        if category in _NEUTRALIZE_CATEGORIES:
            cleaned = pattern.sub(f"[REMOVED: untrusted text matching {pid} ({category})]", cleaned)
    return cleaned


def scan_input(text: str, *, source: str = "unknown") -> InputScan:
    """Scan untrusted text destined for a model prompt.

    `source` is a free-text label for where the text came from (e.g. "operator_question",
    "finding.gap_description"). It is not used in any verdict -- it exists so a recorded
    hit says which channel was attacked, which is the thing an incident responder needs
    and cannot recover afterwards.
    """
    if not text:
        return InputScan(verdict="clear", neutralized="", input_sha256=_sha256(""))

    hits = tuple(
        PatternHit(pattern_id=pid, category=cat, severity=sev, excerpt=_truncate(match.group(0)))
        for pid, cat, sev, pattern in _INPUT_PATTERNS
        if (match := pattern.search(text))
    )
    return InputScan(
        verdict=_worst(hits),
        hits=hits,
        neutralized=_neutralize(text, hits),
        input_sha256=_sha256(text),
    )


def scan_output(
    text: str,
    *,
    allowed_evidence_ids: frozenset[str] | set[str] | tuple[str, ...] = (),
    known_identifiers: frozenset[str] | set[str] | tuple[str, ...] = (),
    contract: ProhibitionContract | None = None,
    citation_pattern: re.Pattern[str] = re.compile(r"\b[A-Z]{1,4}-\d{3,}\b"),
) -> OutputScan:
    """Scan generated text before it reaches a human.

    `known_identifiers` are id-shaped tokens that legitimately appear in the record
    WITHOUT being citations -- a batch id (`B-001`), a case id, a run id. They are not
    citable evidence, but naming the thing the record is about is not fabrication, and
    treating it as such blocks correct answers. Found live the first time this ran
    against a real batch_review run: the model wrote "Batch B-001 has complete findings",
    the citation pattern matched `B-001`, and a good answer was withheld.

    Kept as a separate argument rather than folded into `allowed_evidence_ids` so the
    distinction stays visible at every call site: these tokens are permitted to APPEAR,
    they are not permitted to be CITED as evidence. Collapsing the two would quietly
    turn every identifier in a record into a valid citation.

    Three checks, in the order that matters:

      1. Citation fabrication. Every id-shaped token in the answer must exist in
         `allowed_evidence_ids` or `known_identifiers`. A fabricated id is `blocked`
         unconditionally -- it is the exact failure the "every claim traceable to
         evidence" non-negotiable exists to prevent, and unlike a stylistic slip it
         cannot be safely shown to a human with a warning attached, because the citation
         is what makes the claim checkable in the first place. Pass empty sets to skip
         this check (only appropriate when the text is not supposed to cite anything).
      2. Prohibited disposition terms, delegated to the caller-supplied
         ProhibitionContract so this shares one source of truth with ADR-004 layer 3.
      3. Prompt-guard patterns: instruction compliance, role abandonment, and claimed
         decision authority -- the observable symptoms of a successful injection.
    """
    hits = tuple(
        PatternHit(pattern_id=pid, category=cat, severity=sev, excerpt=_truncate(match.group(0)))
        for pid, cat, sev, pattern in _OUTPUT_PATTERNS
        if (match := pattern.search(text))
    )

    lowered = text.lower()
    leaked = tuple(
        PatternHit(
            pattern_id="PG-004", category="system_prompt_leak", severity="high",
            excerpt=_truncate(marker),
        )
        for marker in _SYSTEM_PROMPT_MARKERS
        if marker in lowered
    )
    hits += leaked

    fabricated: tuple[str, ...] = ()
    if allowed_evidence_ids or known_identifiers:
        allowed = frozenset(allowed_evidence_ids) | frozenset(known_identifiers)
        cited = {m.group(0) for m in citation_pattern.finditer(text)}
        fabricated = tuple(sorted(cited - allowed))
        if fabricated:
            hits += (
                PatternHit(
                    pattern_id="PG-005", category="citation_fabrication", severity="high",
                    excerpt=_truncate(", ".join(fabricated)),
                ),
            )

    banned: tuple[str, ...] = ()
    if contract is not None:
        banned = tuple(term for term in contract.banned_terms if term.lower() in lowered)
        if banned:
            hits += (
                PatternHit(
                    pattern_id="PG-006", category="prohibited_disposition", severity="high",
                    excerpt=_truncate(", ".join(banned)),
                ),
            )

    return OutputScan(
        verdict=_worst(hits),
        hits=hits,
        fabricated_citations=fabricated,
        matched_banned_terms=banned,
    )


def hits_as_dicts(hits: tuple[PatternHit, ...]) -> list[dict[str, str]]:
    """JSON-safe form for API responses and audit records."""
    return [
        {"pattern_id": h.pattern_id, "category": h.category, "severity": h.severity, "excerpt": h.excerpt}
        for h in hits
    ]
