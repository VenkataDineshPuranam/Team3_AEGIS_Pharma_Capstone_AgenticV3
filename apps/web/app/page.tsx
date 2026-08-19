"use client";

import Link from "next/link";
import { PageBody, PageHeader } from "@/components/layout/AppShell";
import { useAuth } from "@/components/layout/AuthContext";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, NotAvailable } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EmptyState, ErrorState, Notice, SkeletonRows, SkeletonText } from "@/components/ui/States";
import { StatTile, DistributionBar } from "@/components/dashboard/StatTile";
import { Identifier, StateBadge, WorkflowChip, toneForDependency } from "@/components/domain/Chips";
import { useApiResource, useVisiblePolling } from "@/hooks/useApiResource";
import {
  getDashboard,
  getHealthDetail,
  getQueue,
  getRoleCatalog,
  getRunHistory,
  type DependencyHealth,
} from "@/lib/api";
import {
  ABSTENTION_EXPLANATIONS,
  formatAge,
  formatCurrency,
  formatDateTime,
  formatNumber,
  formatPercent,
  humanize,
} from "@/lib/format";

/**
 * Overview — the ten-second read.
 *
 * Ordered by what an operator needs to know first: is anything waiting for me, is the
 * system healthy, then how it has been behaving. Every number here comes from
 * /api/dashboard (the real audit store and Redis counters) or /api/queue. Nothing on this
 * page is computed from an assumption, and any metric the backend cannot supply renders
 * as "Not available" rather than a zero.
 */
export default function OverviewPage() {
  const pollMs = useVisiblePolling(15_000);
  const { session } = useAuth();

  const queue = useApiResource((s) => getQueue(undefined, s), [], { pollMs });
  const dashboard = useApiResource((s) => getDashboard(undefined, s), [], { pollMs: 30_000 });
  const health = useApiResource((s) => getHealthDetail(s), [], { pollMs: 60_000 });
  const recent = useApiResource((s) => getRunHistory({ limit: 8 }, s), [], { pollMs: 30_000 });
  const roles = useApiResource((s) => getRoleCatalog(s), []);

  const pending = queue.data;
  const states = dashboard.data?.terminal_states;
  const unhealthy =
    health.data?.dependencies.filter(
      (d) => d.status === "unavailable" || d.status === "degraded",
    ) ?? [];

  // The home page is the one screen every role lands on first, so its framing is the one
  // place worth tailoring per role rather than showing the same generic sentence to
  // everyone -- Super Admin genuinely uses this differently (system-wide oversight, no
  // decide authority) than an approver role does (accountable for specific decisions).
  const myRole = session ? roles.data?.[session.role] : undefined;
  const headerDescription = session
    ? session.role === "Super Admin"
      ? `Signed in as ${session.display_name} — Super Admin. Full cross-workflow visibility for system oversight; this account cannot approve, reject, or veto anything (by design — see Governance).`
      : `Signed in as ${session.display_name} — ${session.role}. ${myRole?.product_use ?? "Governed AI decision support across six regulated workflows."}`
    : "Governed AI decision support across six regulated workflows. Every finding is evidence-backed, every terminal decision is made by an accountable human.";

  return (
    <>
      <PageHeader
        title={session ? `Welcome back, ${session.display_name.split(" ").pop()}` : "Overview"}
        description={headerDescription}
      />

      <PageBody className="space-y-6">
        {session?.role === "Super Admin" && (
          <Notice tone="info" title="Super Admin: read-only, system-wide">
            You can see every workflow below with nothing filtered out. This role has no
            approve, reject, or veto authority anywhere in the system — see{" "}
            <Link href="/compliance" className="underline underline-offset-2">Compliance</Link> and{" "}
            <Link href="/coverage" className="underline underline-offset-2">Evaluation &amp; Security</Link>{" "}
            for the two additional sections only Super Admin can see.
          </Notice>
        )}
        {(session?.role === "Auditor" || session?.role === "Unblinding authority") && (
          <Notice tone="info" title={`${session.role}: read-only oversight`}>
            This role has no approve, reject, or veto authority anywhere in the system — see{" "}
            {myRole?.must_never ?? "the role catalog"} in{" "}
            <Link href="/governance" className="underline underline-offset-2">Governance</Link>.
            Your account exists to review the record, not act on it: see every finalized run in{" "}
            <Link href="/runs" className="underline underline-offset-2">Run History</Link>, where
            you can also export the full audit report as a CSV.
          </Notice>
        )}
        {unhealthy.length > 0 && (
          <Notice tone="warning" title="A dependency needs attention">
            {unhealthy.map((d) => d.name).join(", ")} —{" "}
            <Link href="/health" className="underline underline-offset-2">
              see System Health
            </Link>
            .
          </Notice>
        )}

        {/* --- what needs attention now ---------------------------------- */}
        <section aria-labelledby="attention-heading">
          <h2 id="attention-heading" className="sr-only">
            Requiring attention
          </h2>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile
              label="Awaiting decision"
              value={queue.loading && !pending ? "—" : (pending?.length ?? null)}
              tone={pending && pending.length > 0 ? "pending" : "neutral"}
              href="/decisions"
              sub={
                pending && pending.length > 0
                  ? `Oldest waiting ${formatAge(pending[0].created_at)}`
                  : "Nothing is blocked on a human"
              }
              unavailableReason="The queue could not be read from the Orchestrator API."
            />
            <StatTile
              label="Runs recorded"
              value={formatNumber(states?.run_count) ?? null}
              sub="In the append-only audit store"
              href="/runs"
            />
            <StatTile
              label="Blocked by guardrail"
              value={formatNumber(dashboard.data?.guardrail_trip.blocked_count) ?? null}
              tone={
                dashboard.data && dashboard.data.guardrail_trip.blocked_count > 0
                  ? "blocked"
                  : "neutral"
              }
              sub={
                dashboard.data?.guardrail_trip.blocked_rate != null
                  ? `${formatPercent(dashboard.data.guardrail_trip.blocked_rate)} of all runs`
                  : undefined
              }
              href="/runs?terminal_state=blocked"
            />
            <StatTile
              label="Cache hit rate"
              value={formatPercent(dashboard.data?.cache.hit_rate ?? null) ?? null}
              tone="info"
              sub={
                dashboard.data?.cache.status === "REDIS_UNAVAILABLE"
                  ? "Redis unavailable — runs proceed uncached"
                  : dashboard.data?.cache.hits != null
                    ? `${formatNumber(dashboard.data.cache.hits)} hits / ${formatNumber(dashboard.data.cache.misses)} misses`
                    : undefined
              }
              unavailableReason="Redis is not reachable, so no counters are available."
            />
          </div>
        </section>

        <div className="grid gap-6 xl:grid-cols-3">
          {/* --- decision queue preview --------------------------------- */}
          <Card className="xl:col-span-2">
            <CardHeader
              title="Decision queue"
              description="Runs paused at a human-in-the-loop interrupt"
              actions={
                <Link
                  href="/decisions"
                  className="text-[13px] font-medium text-[var(--brand)] hover:underline"
                >
                  Open queue →
                </Link>
              }
            />
            {queue.error ? (
              <CardBody>
                <ErrorState
                  message={queue.error.userMessage}
                  hint={
                    <>
                      The Orchestrator API should be running at{" "}
                      <code className="font-mono">
                        {process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}
                      </code>
                      . Start it with{" "}
                      <code className="font-mono">
                        uvicorn services.api.main:app --port 8000
                      </code>
                      .
                    </>
                  }
                  action={<Button onClick={queue.refresh}>Try again</Button>}
                />
              </CardBody>
            ) : queue.loading && !pending ? (
              <SkeletonRows rows={3} />
            ) : !pending || pending.length === 0 ? (
              <EmptyState
                title="No decisions are waiting"
                description="Nothing is currently paused for human approval. A run appears here when it reaches its human-in-the-loop interrupt — which every governed workflow must do before it can complete."
                action={
                  <Link
                    href="/workflows"
                    className="inline-flex h-8 items-center rounded-[var(--radius-md)] border border-[var(--border-default)] px-3 text-[13px] font-medium text-[var(--text-primary)] hover:bg-[var(--surface-sunken)]"
                  >
                    Start a run
                  </Link>
                }
              />
            ) : (
              <ul className="divide-y divide-[var(--border-subtle)]">
                {pending.slice(0, 6).map((entry) => (
                  <li key={entry.run_id}>
                    <Link
                      href={`/decisions/${encodeURIComponent(entry.run_id)}`}
                      className="flex items-center gap-3 px-4 py-3 hover:bg-[var(--surface-sunken)] sm:px-5"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <WorkflowChip workflow={entry.workflow} size="xs" />
                          <span className="font-mono text-[13px] font-medium text-[var(--text-primary)]">
                            {entry.subject_id}
                          </span>
                          {entry.required_legs && entry.required_legs.length > 1 && (
                            <Badge tone="pending" size="xs">
                              {entry.approved_legs.length}/{entry.required_legs.length} legs
                            </Badge>
                          )}
                        </div>
                        <p className="mt-1 line-clamp-1 text-[13px] text-[var(--text-secondary)]">
                          {entry.draft_summary ?? "No decision-support summary was produced."}
                        </p>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className="tnum text-xs text-[var(--text-tertiary)]">
                          {formatAge(entry.created_at)}
                        </p>
                        <p className="mt-0.5 max-w-32 truncate text-[11px] text-[var(--text-tertiary)]">
                          {entry.approver_roles[0]}
                        </p>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {/* --- outcome distribution ----------------------------------- */}
          <Card>
            <CardHeader
              title="Run outcomes"
              description={
                states ? `${formatNumber(states.run_count)} recorded runs` : "Loading…"
              }
            />
            <CardBody>
              {dashboard.error ? (
                <p className="text-sm text-[var(--text-tertiary)]">
                  <NotAvailable reason={dashboard.error.userMessage} />
                </p>
              ) : !states ? (
                <SkeletonText lines={4} />
              ) : (
                <>
                  <DistributionBar
                    total={states.run_count}
                    segments={[
                      {
                        label: "completed",
                        value: states.by_terminal_state.completed ?? 0,
                        className: "bg-[var(--status-ok-fg)]",
                      },
                      {
                        label: "abstained",
                        value: states.by_terminal_state.abstained ?? 0,
                        className: "bg-[var(--status-abstained-fg)]",
                      },
                      {
                        label: "refused",
                        value: states.by_terminal_state.refused ?? 0,
                        className: "bg-[var(--status-refused-fg)]",
                      },
                      {
                        label: "blocked",
                        value: states.by_terminal_state.blocked ?? 0,
                        className: "bg-[var(--status-blocked-fg)]",
                      },
                    ]}
                  />
                  <dl className="mt-4 space-y-2">
                    {Object.entries(states.by_terminal_state)
                      .sort((a, b) => b[1] - a[1])
                      .map(([state, count]) => (
                        <div key={state} className="flex items-center justify-between gap-3">
                          <dt>
                            <StateBadge state={state} size="xs" />
                          </dt>
                          <dd className="tnum text-sm font-medium text-[var(--text-primary)]">
                            {formatNumber(count)}
                            <span className="ml-1.5 text-xs font-normal text-[var(--text-tertiary)]">
                              {formatPercent(count / states.run_count, 0)}
                            </span>
                          </dd>
                        </div>
                      ))}
                  </dl>

                  <p className="mt-4 border-t border-[var(--border-subtle)] pt-3 text-[11px] leading-relaxed text-[var(--text-tertiary)]">
                    Abstaining and refusing are correct outcomes, not failures: the system
                    declines to answer rather than answer without sufficient evidence or a
                    loadable policy.
                  </p>
                </>
              )}
            </CardBody>
          </Card>
        </div>

        <div className="grid gap-6 xl:grid-cols-3">
          {/* --- recent activity ---------------------------------------- */}
          <Card className="xl:col-span-2">
            <CardHeader
              title="Recent activity"
              description="Most recently finalized runs"
              actions={
                <Link
                  href="/runs"
                  className="text-[13px] font-medium text-[var(--brand)] hover:underline"
                >
                  Full history →
                </Link>
              }
            />
            {recent.loading && !recent.data ? (
              <SkeletonRows rows={4} />
            ) : recent.error ? (
              <CardBody>
                <p className="text-sm text-[var(--text-tertiary)]">
                  <NotAvailable reason={recent.error.userMessage} />
                </p>
              </CardBody>
            ) : !recent.data?.items.length ? (
              <EmptyState
                title="No runs recorded yet"
                description="The audit store is empty. Every run writes a record here when it finalizes."
              />
            ) : (
              <ul className="divide-y divide-[var(--border-subtle)]">
                {recent.data.items.map((run) => (
                  <li key={run.run_id}>
                    <Link
                      href={`/runs/${encodeURIComponent(run.run_id)}`}
                      className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2.5 hover:bg-[var(--surface-sunken)] sm:px-5"
                    >
                      <StateBadge state={run.terminal_state} size="xs" />
                      <WorkflowChip workflow={run.workflow} size="xs" />
                      {run.subject_id && (
                        <span className="font-mono text-[13px] text-[var(--text-primary)]">
                          {run.subject_id}
                        </span>
                      )}
                      <Identifier value={run.run_id} className="text-[11px]" />
                      {run.abstention_reason && (
                        <span
                          className="text-[11px] text-[var(--text-tertiary)]"
                          title={ABSTENTION_EXPLANATIONS[run.abstention_reason]}
                        >
                          {humanize(run.abstention_reason)}
                        </span>
                      )}
                      <span className="ml-auto tnum text-[11px] text-[var(--text-tertiary)]">
                        {formatDateTime(run.recorded_at)}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {/* --- health + cost ------------------------------------------ */}
          <div className="space-y-6">
            <Card>
              <CardHeader
                title="System health"
                actions={
                  <Link
                    href="/health"
                    className="text-[13px] font-medium text-[var(--brand)] hover:underline"
                  >
                    Details →
                  </Link>
                }
              />
              <CardBody className="space-y-2">
                {health.loading && !health.data ? (
                  <SkeletonText lines={5} />
                ) : health.error ? (
                  <p className="text-sm">
                    <NotAvailable reason={health.error.userMessage} />
                  </p>
                ) : (
                  health.data?.dependencies.map((dep: DependencyHealth) => (
                    <div key={dep.name} className="flex items-center justify-between gap-2">
                      <span className="min-w-0 truncate text-[13px] text-[var(--text-secondary)]">
                        {dep.name}
                      </span>
                      <Badge tone={toneForDependency(dep.status)} size="xs">
                        {humanize(dep.status)}
                      </Badge>
                    </div>
                  ))
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Model cost" description="Measured from recorded runs" />
              <CardBody>
                {dashboard.data ? (
                  <dl className="space-y-2.5 text-sm">
                    <Row
                      label="Runs with token data"
                      value={formatNumber(dashboard.data.cost.run_count)}
                    />
                    <Row
                      label="Mean cost / run"
                      value={formatCurrency(dashboard.data.cost.mean_cost_usd_per_run)}
                    />
                    <Row
                      label="p95 cost / run"
                      value={formatCurrency(dashboard.data.cost.p95_cost_usd_per_run)}
                    />
                    <Row
                      label="Total, all recorded runs"
                      value={formatCurrency(dashboard.data.cost.total_cost_usd, 2)}
                    />
                    <Row
                      label="Mean tokens / run"
                      value={formatNumber(dashboard.data.cost.mean_tokens_per_run)}
                    />
                    <Row
                      label="p95 tokens / run"
                      value={formatNumber(dashboard.data.cost.p95_tokens_per_run)}
                    />
                    <Row
                      label="Mean model calls / run"
                      value={formatNumber(dashboard.data.cost.mean_llm_calls_per_run, 2)}
                    />
                  </dl>
                ) : (
                  <SkeletonText lines={4} />
                )}
                <p className="mt-4 border-t border-[var(--border-subtle)] pt-3 text-[11px] leading-relaxed text-[var(--text-tertiary)]">
                  Cost is a configured estimate ({dashboard.data ? formatCurrency(dashboard.data.cost.price_per_1k_input_usd, 4) : "$0.0025"}/1K
                  input, {dashboard.data ? formatCurrency(dashboard.data.cost.price_per_1k_output_usd, 4) : "$0.01"}/1K output tokens against
                  recorded token counts) — not a reconciled Azure invoice figure. Per-node
                  token breakdown is not computable from the audit store, which holds run
                  totals only; that granularity lives in LangSmith traces.
                </p>
              </CardBody>
            </Card>
          </div>
        </div>
      </PageBody>
    </>
  );
}

function Row({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-[13px] text-[var(--text-secondary)]">{label}</dt>
      <dd className="tnum font-medium text-[var(--text-primary)]">
        {value ?? <NotAvailable />}
      </dd>
    </div>
  );
}
