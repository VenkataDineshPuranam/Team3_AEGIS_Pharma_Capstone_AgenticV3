/**
 * Wire types -- a hand-maintained mirror of services/api/schemas.py.
 *
 * These are the API's contract, not the domain model. Where a Python field is
 * `X | None`, it is `X | null` here (not `X | undefined`): the difference between "the
 * backend sent null" and "the key was absent" is exactly the difference between "not
 * recorded" and "this client is out of date", and collapsing them would let a UI silently
 * render a missing field as an absent one.
 */

export type Workflow =
  | "batch_review"
  | "pv_intake"
  | "supply_planning"
  | "research_review"
  | "clinical_integrity"
  | "regulatory_completeness";

export type RunStatus =
  | "pending_approval"
  | "completed"
  | "abstained"
  | "blocked"
  | "refused";

export type DecisionAction = "approved" | "rejected" | "veto" | "timed_out";
export type SupplyLeg = "planning" | "quality";

export interface SessionInfo {
  token: string;
  user_id: string;
  display_name: string;
  role: string;
  expires_at: string;
}

export interface RoleCatalogEntry {
  product_use: string;
  must_never: string;
}

export interface DraftClaim {
  text: string;
  cites: string[];
}

export interface EvidenceRef {
  evidence_id: string;
  source: string;
  status: string;
  effective_date: string;
  jurisdiction: string | null;
  supersedes: string | null;
  content_excerpt: string;
}

export interface EvidenceCatalogItem {
  evidence_id: string;
  source: string;
  status: string;
  citable: boolean;
  authority: string | null;
  jurisdiction: string | null;
  effective_date: string | null;
  supersedes: string | null;
  superseded_by: string | null;
  content_excerpt: string;
}

/** batch_review's domain_payload (packages/domain/payloads.py: BatchPayload). */
export interface BatchPayload {
  batch_id: string;
  reconciliation_complete: boolean;
  findings: {
    category: string;
    status: "complete" | "gap" | "conflict";
    evidence_ids: string[];
    gap_description: string | null;
  }[];
}

/** pv_intake's domain_payload (PVPayload). */
export interface PVPayload {
  case_id: string;
  duplicate_suspected: boolean;
  comparison_window_version: string;
  candidates: {
    candidate_case_id: string;
    similarity_score: number;
    matched_fields: string[];
  }[];
  normalization_suggestions: {
    normalized_term: string;
    confidence: number;
    terminology_source: string;
  }[];
  terminology_table_version: string;
}

/** supply_planning's domain_payload (SupplyPayload). */
export interface SupplyPayload {
  product_id: string;
  options: {
    option_id: string;
    description: string;
    constraints_satisfied: string[];
    cold_chain_evidence_ids: string[];
    transport_notes: string;
  }[];
  constraint_set: {
    market_authorization_scope: string[];
    cold_chain_requirements: string[];
    trial_demand_reservations: string[];
    compassionate_use_constraints: string[];
    cmo_capacity_window: string | null;
  };
  inventory_snapshot_version: string;
}

/** Shared shape across research_review/clinical_integrity/regulatory_completeness --
 * each mirrors BatchPayload's exact (subject_field, reconciliation_complete, findings)
 * structure, only the subject-id field name and category enum differ. */
interface FindingsPayload {
  reconciliation_complete: boolean;
  findings: {
    category: string;
    status: "complete" | "gap" | "conflict";
    evidence_ids: string[];
    gap_description: string | null;
  }[];
}

export interface ResearchPayload extends FindingsPayload {
  research_id: string;
}

export interface ClinicalPayload extends FindingsPayload {
  protocol_id: string;
}

export interface RegulatoryPayload extends FindingsPayload {
  submission_id: string;
}

export type DomainPayload =
  | BatchPayload
  | PVPayload
  | SupplyPayload
  | ResearchPayload
  | ClinicalPayload
  | RegulatoryPayload;

/** services/integration/hitl_timer.py's tier -- display only, recomputed on every poll. */
export type HitlTier = "T0" | "T1" | "T2" | "T3";

export interface HitlTimerInfo {
  tier: HitlTier;
  label: string;
  /** 1 (lowest) .. 4 (highest / red). */
  severity: number;
  hours_elapsed: number;
  hours_to_next_tier: number | null;
}

export interface QueueEntry {
  run_id: string;
  workflow: Workflow;
  subject_id: string;
  requester_role: string;
  approver_roles: string[];
  required_legs: string[] | null;
  approved_legs: string[];
  draft_summary: string | null;
  draft_claims: DraftClaim[];
  created_at: string;
  evidence: EvidenceRef[];
  domain_payload: DomainPayload | null;
  evidence_accounting: Record<string, unknown> | null;
  hitl_timer: HitlTimerInfo;
}

export interface RunResult {
  run_id: string;
  workflow: Workflow;
  status: RunStatus;
  terminal_state: string | null;
  abstention_reason: string | null;
  llm_calls: number | null;
  draft_summary: string | null;
  draft_claims: DraftClaim[];
  approver_roles: string[];
  required_legs: string[] | null;
  approved_legs: string[];
  veto_recorded: boolean;
}

export interface AuditedRun {
  run_id: string;
  workflow: string;
  terminal_state: string;
  abstention_reason: string | null;
  trace_id: string | null;
  policy_contract_version: string | null;
  recorded_at: string;
  llm_calls: number | null;
  tokens_in: number | null;
  tokens_out: number | null;
  subject_id: string | null;
  requester_role: string | null;
  approver_roles: string[] | null;
  hitl_status: string | null;
  evidence_ids: string[] | null;
}

export interface AuditEvent {
  at: string;
  event_type: string;
  actor: string | null;
  role: string | null;
  action: string;
  metadata: Record<string, unknown>;
}

export interface HumanAction {
  role: string;
  tier_at_action: string;
  action: string;
  justification: string;
  recorded_at: string;
}

export interface RunDetail {
  run_id: string;
  pending: QueueEntry | null;
  audit: AuditedRun | null;
  timeline: AuditEvent[];
  human_actions: HumanAction[];
  decision_support_available: boolean;
  decision_support_unavailable_reason: string | null;
}

export interface RunHistoryPage {
  items: AuditedRun[];
  total: number;
  limit: number;
  offset: number;
}

export interface DashboardResponse {
  workflow: string | null;
  cost: {
    run_count: number;
    mean_tokens_per_run: number | null;
    p95_tokens_per_run: number | null;
    mean_llm_calls_per_run: number | null;
  };
  guardrail_trip: {
    run_count: number;
    blocked_count: number;
    blocked_rate: number | null;
  };
  terminal_states: {
    run_count: number;
    by_terminal_state: Record<string, number>;
    by_abstention_reason: Record<string, number>;
  };
  cache: {
    hits: number | null;
    misses: number | null;
    hit_rate: number | null;
    status?: string;
  };
}

export interface GovernanceSnapshot {
  policy_contract_version: string;
  prohibited_actions: {
    status: string;
    source: string;
    enforcement: string[];
    by_workflow: Record<
      string,
      { workflow: string; banned_terms: string[]; banned_field_names: string[] }
    >;
  };
  hitl_rules: {
    source: string;
    escalation_ladder_hours: Record<string, number>;
    invariants: string[];
    clock_status: string;
  };
  approver_roles: Record<
    string,
    {
      primary: string[];
      escalation?: string;
      veto_role?: string;
      required_legs?: string[];
      structure: string;
    }
  >;
  evidence_authority: {
    source: string;
    citable_statuses: string[];
    enforcement: string;
    broadening_ceiling_per_run: number;
    cache_rule: string;
  };
  authentication: {
    status: string;
    detail: string;
    planned: string;
    roles_referenced_by_the_domain: string[];
  };
}

export type DependencyStatus = "ok" | "degraded" | "unavailable" | "not_configured";

export interface DependencyHealth {
  name: string;
  status: DependencyStatus;
  detail: string | null;
  latency_ms: number | null;
}

export interface HealthDetail {
  api: DependencyHealth;
  dependencies: DependencyHealth[];
  audit_store: {
    row_counts: Record<string, number>;
    latest_run_recorded_at: string | null;
    db_path: string;
  };
  checked_at: string;
}

export interface EvidenceStats {
  by_status: Record<string, number>;
  total: number;
  citable_total: number;
  supersedes_edges: number;
}

// --- Record Assistant (Stage 23) ---------------------------------------------

export interface PromptGuardHit {
  pattern_id: string;
  category: string;
  severity: "low" | "medium" | "high";
  excerpt: string;
}

export interface RecordChatGuard {
  prompt_guard_version: string;
  input_verdict: "clear" | "flagged" | "blocked";
  output_verdict: "clear" | "flagged" | "blocked";
  input_hits: PromptGuardHit[];
  /** Injection-shaped text found INSIDE the record itself (threat catalogue T-01). */
  record_hits: PromptGuardHit[];
  output_hits: PromptGuardHit[];
  refused: boolean;
}

export interface RecordChatNextStep {
  step: string;
  owner: string;
  /** The step the run is actually stuck on, as opposed to context. */
  blocking: boolean;
}

/**
 * `record` and `next_steps` are computed from the run with no model involved;
 * `summary`, `answer` and `next_steps_explanation` are model-written prose over exactly
 * those facts. The UI keeps them visually distinct for the same reason the API keeps them
 * in separate fields -- an operator must be able to tell which half can be wrong.
 */
export interface RecordChatResponse {
  run_id: string;
  record: Record<string, unknown>;
  next_steps: RecordChatNextStep[];
  summary: string;
  answer: string;
  next_steps_explanation: string;
  cites: string[];
  llm_available: boolean;
  llm_unavailable_reason: string | null;
  guard: RecordChatGuard;
}

// --- Notifications (Stage 23) --------------------------------------------------

export interface NotificationItem {
  run_id: string;
  workflow: string;
  tier: string;
  severity: number;
  evaluated_at: string;
  subject_id: string | null;
  approver_roles: string[] | null;
}

// --- Chaos drills (ADR-007 lab injectors) --------------------------------------

export interface ChaosDrillAssertion {
  name: string;
  passed: boolean;
  detail: string;
}

export interface ChaosDrillLastResult {
  drill_id: string;
  passed: boolean;
  overall_verdict: string;
  run_at: string;
  duration_ms: number;
  outcome_summary: string;
  observed: Record<string, unknown>;
}

export interface ChaosDrillExperiment {
  id: string;
  title: string;
  adr_row: string;
  ui_runnable: boolean;
  workflow: string;
  runbook: string | null;
  last_result: ChaosDrillLastResult | null;
}

export interface ChaosDrillCatalog {
  capabilities: { can_run: boolean };
  experiments: ChaosDrillExperiment[];
}

export interface ChaosDrillResult {
  drill_id: string;
  experiment_id: string;
  passed: boolean;
  overall_verdict: string;
  assertions: ChaosDrillAssertion[];
  observed: Record<string, unknown>;
  outcome_summary: string;
  duration_ms: number;
  run_at: string;
  run_by_user_id: string;
  run_by_display_name: string;
  run_by_role: string;
}

export interface ChaosDrillSummary {
  drill_id: string;
  experiment_id: string;
  run_at: string;
  run_by_display_name: string;
  run_by_role: string;
  passed: boolean;
  overall_verdict: string;
  duration_ms: number;
  outcome_summary: string;
  observed: Record<string, unknown>;
}
