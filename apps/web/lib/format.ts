import type { BadgeTone } from "@/components/ui/Badge";
import type { Workflow } from "@/lib/api";

/**
 * Formatting and vocabulary.
 *
 * The label maps here are the product's voice. They exist in one place because a screen
 * that calls a state "blocked" while another calls the same state "prohibited" makes the
 * system look less trustworthy than it is.
 */

export const WORKFLOW_LABELS: Record<Workflow, string> = {
  batch_review: "GxP Batch Review",
  pv_intake: "PV Intake & Signal Support",
  supply_planning: "Supply & Cold-Chain Planning",
  research_review: "Research & Preclinical Review",
  clinical_integrity: "Clinical Trial Integrity",
  regulatory_completeness: "Regulatory Submission Completeness",
};

export const WORKFLOW_SHORT: Record<Workflow, string> = {
  batch_review: "Batch Review",
  pv_intake: "PV Intake",
  supply_planning: "Supply Planning",
  research_review: "Research Review",
  clinical_integrity: "Clinical Integrity",
  regulatory_completeness: "Regulatory",
};

/** The subject a workflow reasons about -- shown as the column header, not "subject_id". */
export const WORKFLOW_SUBJECT_LABEL: Record<Workflow, string> = {
  batch_review: "Batch",
  pv_intake: "Case",
  supply_planning: "Product",
  research_review: "Research item",
  clinical_integrity: "Protocol",
  regulatory_completeness: "Submission",
};

/**
 * What each workflow may and may not conclude. Rendered on the decision workspace so the
 * approver sees the boundary at the moment they act, not only in documentation.
 * Sourced from the product definition and mirrored by the policy contract's banned terms.
 */
export const WORKFLOW_BOUNDARY: Record<Workflow, { produces: string; neverDoes: string[] }> = {
  batch_review: {
    produces:
      "Reconciliation findings and release-packet completeness for a human certifier. Certification remains human-only.",
    neverDoes: [
      "Release, reject, reprocess, relabel or recall a batch",
      "Recommend a disposition of any kind",
    ],
  },
  pv_intake: {
    produces:
      "Intake support: duplicate candidates, terminology normalization suggestions, and reporting-clock reconstruction. Safety determinations remain human-only.",
    neverDoes: [
      "Determine seriousness, causality, expectedness or reportability",
      "Confirm or validate a safety signal",
    ],
  },
  supply_planning: {
    produces:
      "Constraint-satisfying planning options with rationale. Options are proposals; execution is a separate, human process outside this system.",
    neverDoes: [
      "Allocate, reserve, or change the status of inventory",
      "Ship product or initiate a recall",
    ],
  },
  research_review: {
    produces:
      "Reconciliation findings across assay comparability, compound identity, cohort representativeness, image integrity, model-qualification evidence and target-evidence concordance, for a human Research/Portfolio reviewer.",
    neverDoes: [
      "Qualify a model or approve its intended use",
      "Validate a target or advance a compound",
    ],
  },
  clinical_integrity: {
    produces:
      "Reconciliation findings across protocol-version conformance, eligibility, randomization/blinding integrity, consent status, device data and endpoint adjudication, for a human clinical/medical monitor.",
    neverDoes: [
      "Determine participant eligibility or take an unblinding action",
      "Dispose of a protocol deviation",
    ],
  },
  regulatory_completeness: {
    produces:
      "Reconciliation findings across identity consistency, labeling, commitment tracking, submission-sequence completeness and variation-classification evidence, for a human Regulatory Affairs reviewer.",
    neverDoes: [
      "Classify a variation or determine submission readiness",
      "Make any regulatory determination",
    ],
  },
};

export function workflowTone(workflow: string): string {
  return (
    {
      batch_review:
        "text-[var(--workflow-batch-fg)] bg-[var(--workflow-batch-bg)] border-[var(--workflow-batch-border)]",
      pv_intake:
        "text-[var(--workflow-pv-fg)] bg-[var(--workflow-pv-bg)] border-[var(--workflow-pv-border)]",
      supply_planning:
        "text-[var(--workflow-supply-fg)] bg-[var(--workflow-supply-bg)] border-[var(--workflow-supply-border)]",
      research_review:
        "text-[var(--workflow-research-fg)] bg-[var(--workflow-research-bg)] border-[var(--workflow-research-border)]",
      clinical_integrity:
        "text-[var(--workflow-clinical-fg)] bg-[var(--workflow-clinical-bg)] border-[var(--workflow-clinical-border)]",
      regulatory_completeness:
        "text-[var(--workflow-regulatory-fg)] bg-[var(--workflow-regulatory-bg)] border-[var(--workflow-regulatory-border)]",
    }[workflow] ?? "text-[var(--text-secondary)] bg-[var(--surface-sunken)] border-[var(--border-default)]"
  );
}

/** Terminal states, in the product's own words rather than the enum's. */
export const TERMINAL_STATE_LABELS: Record<string, string> = {
  completed: "Completed",
  abstained: "Abstained",
  blocked: "Blocked by guardrail",
  refused: "Refused",
  pending_approval: "Awaiting decision",
};

export function terminalStateTone(state: string | null | undefined): BadgeTone {
  switch (state) {
    case "completed":
      return "ok";
    case "blocked":
      return "blocked";
    case "refused":
      return "refused";
    case "abstained":
      return "abstained";
    case "pending_approval":
      return "pending";
    default:
      return "neutral";
  }
}

/**
 * HITL wait-severity, from services/integration/hitl_timer.py's tier -- display only,
 * recomputed on every poll. Reaching T2 does not widen who is authorized to decide; it is
 * a visual severity signal, not an access change.
 */
export const HITL_TIER_TONE: Record<string, BadgeTone> = {
  T0: "neutral",
  T1: "pending",
  T2: "refused",
  T3: "blocked",
};

export const HITL_TIER_NEXT_STEP: Record<string, string> = {
  T0: "On time — no action needed yet.",
  T1: "Past the 8-hour reminder threshold. Still fully valid to decide.",
  T2: "Past the 16-hour escalation threshold. Waiting long enough that a second reviewer should take a look.",
  T3: "Past the 24-hour expiry threshold. If this reaches a real timeout, the run abstains — a timeout is never an implicit approval.",
};

/**
 * Why a run stopped, in plain language. Every key here is a real `abstention_reason`
 * value written by the graphs -- an unknown reason falls through to the raw value rather
 * than being hidden, so a new backend reason shows up instead of disappearing.
 */
export const ABSTENTION_EXPLANATIONS: Record<string, string> = {
  insufficient_evidence:
    "No citable evidence was found, even after the one permitted scope-preserving broadening. The system abstained rather than answer without support.",
  dependency_unavailable:
    "A required tool or data source could not be reached. The system abstained rather than proceed on partial information.",
  degraded_mode:
    "The language model provider was unreachable. The system abstained rather than guess; any deterministic findings already computed are retained.",
  cap_exceeded:
    "The run reached its maximum of 6 model calls without the Critic approving an output. Treated as an engineering defect, not a domain conclusion.",
  hitl_timeout:
    "The approval window expired. No action was taken — a timeout is never an implicit approval.",
  prohibited_action:
    "The generated text matched a prohibited-action term for this workflow. The output was blocked before any human saw it.",
  prohibition_adjacent:
    "The Critic judged the draft to be adjacent to a prohibited action. This is never retried — the run was blocked.",
  fail_closed:
    "The versioned policy contract could not be loaded. The system refuses rather than proceed on a stale or default policy.",
  gate_defect:
    "The evidence gate detected a non-citable item that should have been filtered upstream. The run was halted as untrustworthy.",
};

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

/** Compact age, for queue rows where "how long has this been waiting" is the question. */
export function formatAge(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ${minutes % 60}m`;
  return `${Math.floor(hours / 24)}d ${hours % 24}h`;
}

export function formatNumber(n: number | null | undefined, digits = 0): string | null {
  if (n === null || n === undefined || Number.isNaN(n)) return null;
  return n.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function formatPercent(ratio: number | null | undefined, digits = 1): string | null {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return null;
  return `${(ratio * 100).toFixed(digits)}%`;
}

/** USD, with enough precision to show a sub-cent per-run cost meaningfully. */
export function formatCurrency(amount: number | null | undefined, digits = 4): string | null {
  if (amount === null || amount === undefined || Number.isNaN(amount)) return null;
  return `$${amount.toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

/** Snake_case backend value -> human words, for labels with no curated mapping. */
export function humanize(value: string): string {
  return value.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
}

// --- evidence semantics ----------------------------------------------------

export type EvidenceAuthority = "AUTHORITATIVE" | "DRAFT" | "UNTRUSTED" | "SUPERSEDED" | "NOT CITABLE";

/**
 * Map a raw status to the four semantic states Phase 9 requires.
 *
 * `citable` comes from the backend, which computes it from the same rule the retrieval
 * tool enforces. It is used here rather than re-derived, so this UI cannot come to a
 * different conclusion about usability than the system that enforces it.
 *
 * Note `local_approved`: it reads as approved but is NOT in the retrieval tool's citable
 * set, so it surfaces as NOT CITABLE. That is the honest answer -- a run cannot retrieve
 * it -- and it is exactly the case a hand-written status map would get wrong.
 */
export function evidenceAuthority(status: string, citable: boolean): EvidenceAuthority {
  if (status === "untrusted") return "UNTRUSTED";
  if (status === "superseded") return "SUPERSEDED";
  if (!citable) return "NOT CITABLE";
  if (status === "draft") return "DRAFT";
  return "AUTHORITATIVE";
}

export function evidenceTone(authority: EvidenceAuthority): BadgeTone {
  switch (authority) {
    case "AUTHORITATIVE":
      return "authoritative";
    case "DRAFT":
      return "draft-evidence";
    case "UNTRUSTED":
      return "untrusted";
    case "SUPERSEDED":
      return "superseded";
    case "NOT CITABLE":
      return "blocked";
  }
}

export const EVIDENCE_AUTHORITY_MEANING: Record<EvidenceAuthority, string> = {
  AUTHORITATIVE: "Approved and current. A run may cite this.",
  DRAFT: "Citable, but not yet approved. Weigh accordingly.",
  UNTRUSTED: "Excluded from retrieval. No run can cite this, and neither should you.",
  SUPERSEDED: "Replaced by a newer document. Excluded from retrieval.",
  "NOT CITABLE": "Outside the citable status set enforced by evidence retrieval. No run can cite this.",
};
