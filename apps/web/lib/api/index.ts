/**
 * Typed endpoint functions. One per API route, no ad-hoc fetch calls anywhere else in the
 * app -- so the no-retry-on-human-action rule in client.ts cannot be bypassed by a page
 * that reaches for `fetch` directly.
 */
import { mutate, mutatePublic, read } from "./client";
import type {
  ComplianceSnapshot,
  DashboardResponse,
  DecisionAction,
  DemoAccount,
  EvidenceCatalogItem,
  EvidenceStats,
  GovernanceSnapshot,
  HealthDetail,
  NotificationItem,
  QueueEntry,
  RecordChatResponse,
  RoleCatalogEntry,
  RunDetail,
  RunHistoryPage,
  RunResult,
  SessionInfo,
  SupplyLeg,
  Workflow,
  ChaosDrillCatalog,
  ChaosDrillResult,
  ChaosDrillSummary,
} from "./types";
import type { EvalScorecard, InjectCoverage } from "./coverage-types";

export * from "./types";
export * from "./coverage-types";
export { ApiError } from "./client";

function query(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

// --- auth --------------------------------------------------------------------

export const login = (user_id: string, password: string) =>
  mutatePublic<SessionInfo>("/api/auth/login", { user_id, password });

export const logout = () => mutate<{ status: string }>("/api/auth/logout", {});

export const getRoleCatalog = (signal?: AbortSignal) =>
  read<Record<string, RoleCatalogEntry>>("/api/auth/roles", signal);

export const getDemoAccounts = (signal?: AbortSignal) =>
  read<DemoAccount[]>("/api/auth/demo-accounts", signal);

export const getCompliance = (signal?: AbortSignal) =>
  read<ComplianceSnapshot>("/api/compliance", signal);

// --- reads -----------------------------------------------------------------

export const getQueue = (workflow?: Workflow, signal?: AbortSignal) =>
  read<QueueEntry[]>(`/api/queue${query({ workflow })}`, signal);

export const getDashboard = (workflow?: Workflow, signal?: AbortSignal) =>
  read<DashboardResponse>(`/api/dashboard${query({ workflow })}`, signal);

export const getRunHistory = (
  params: {
    workflow?: string;
    terminal_state?: string;
    subject_id?: string;
    search?: string;
    limit?: number;
    offset?: number;
  },
  signal?: AbortSignal,
) => read<RunHistoryPage>(`/api/runs${query(params)}`, signal);

export const getRunFilters = (signal?: AbortSignal) =>
  read<Record<string, string[]>>(`/api/runs/filters`, signal);

export const getRun = (runId: string, signal?: AbortSignal) =>
  read<RunDetail>(`/api/runs/${encodeURIComponent(runId)}`, signal);

export const getEvidence = (signal?: AbortSignal) =>
  read<EvidenceCatalogItem[]>(`/api/evidence`, signal);

export const getEvidenceStats = (signal?: AbortSignal) =>
  read<EvidenceStats>(`/api/evidence/stats`, signal);

export const getGovernance = (signal?: AbortSignal) =>
  read<GovernanceSnapshot>(`/api/governance`, signal);

export const getHealthDetail = (signal?: AbortSignal) =>
  read<HealthDetail>(`/api/health/detail`, signal);

export const getEvalScorecard = (signal?: AbortSignal) =>
  read<EvalScorecard>(`/api/evals/scorecard`, signal);

export const getInjectCoverage = (signal?: AbortSignal) =>
  read<InjectCoverage>(`/api/coverage/injects`, signal);

/**
 * Recent HITL escalation events -- the notification bell's source
 * (services/integration/hitl_escalation_watch.py's background scan writes these; nothing
 * in the frontend can create one). Unauthenticated on the backend, same as `getQueue`, so
 * this is safe to poll from anywhere in the shell.
 */
export const getNotifications = (limit?: number, signal?: AbortSignal) =>
  read<NotificationItem[]>(`/api/notifications${query({ limit })}`, signal);

export const getChaosDrillExperiments = (signal?: AbortSignal) =>
  read<ChaosDrillCatalog>(`/api/chaos-drill/experiments`, signal);

export const getChaosDrillHistory = (limit?: number, signal?: AbortSignal) =>
  read<ChaosDrillSummary[]>(`/api/chaos-drill/history${query({ limit })}`, signal);

/**
 * Run one ADR-007 lab injector. Uses mutate() (no retry) because each call writes a
 * chaos_drill_run row and may write a DRILL-* agent_run row.
 */
export const runChaosDrillExperiment = (experimentId: string) =>
  mutate<ChaosDrillResult>(
    `/api/chaos-drill/experiments/${encodeURIComponent(experimentId)}/run`,
    {},
  );

// --- writes ----------------------------------------------------------------

export const submitRun = (body: {
  workflow: Workflow;
  subject_id: string;
  requester_role: string;
}) => mutate<RunResult>("/api/runs", body);

/**
 * Record a human decision. Sent once; never retried automatically (see client.ts).
 *
 * `justification` is required by the API and is persisted into the append-only audit
 * record by the graph itself -- it is not held in this client, and not held in React
 * state after this call returns.
 */
/**
 * Ask the Record Assistant about one run. A POST because the question is a body, not
 * because anything is written -- this endpoint decides nothing, records nothing, and
 * cannot resume a paused run.
 *
 * It goes through `mutate()` (no automatic retry) rather than `read()` even though it is
 * read-only: every call costs a model invocation, and silently retrying one that timed
 * out would double the spend against the denial-of-wallet guardrail for an answer the
 * operator can simply ask for again.
 */
export const askAboutRun = (runId: string, question: string, signal?: AbortSignal) =>
  mutate<RecordChatResponse>(`/api/runs/${encodeURIComponent(runId)}/chat`, { question }, signal);

export const decideRun = (
  runId: string,
  body: {
    workflow: Workflow;
    action: DecisionAction;
    justification: string;
    claimed_identity?: string | null;
    leg?: SupplyLeg | null;
  },
) => mutate<RunResult>(`/api/runs/${encodeURIComponent(runId)}/decide`, body);
