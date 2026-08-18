"use client";

import { useRef, useState } from "react";
import { PageBody, PageHeader } from "@/components/layout/AppShell";
import { useAuth } from "@/components/layout/AuthContext";
import { StatTile } from "@/components/dashboard/StatTile";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader, Field } from "@/components/ui/Card";
import { EmptyState, ErrorState, Notice, SkeletonRows, SkeletonText } from "@/components/ui/States";
import { Tabs } from "@/components/ui/Tabs";
import { useApiResource } from "@/hooks/useApiResource";
import {
  ApiError,
  getChaosDrillExperiments,
  getChaosDrillHistory,
  runChaosDrillExperiment,
  type ChaosDrillExperiment,
  type ChaosDrillResult,
} from "@/lib/api";
import { formatDateTime, formatNumber, humanize } from "@/lib/format";

type Tab = "drills" | "history" | "runbooks";

const ASSERTION_LABELS: Record<string, string> = {
  terminal_state: "Terminal state",
  abstention_reason: "Abstention reason",
  deterministic_partial: "Deterministic findings",
  drill_prefix: "Drill run-id prefix",
  no_disposition_language: "No release/disposition language",
  cache_get_called: "Cache get bypassed",
  cache_set_called: "Cache set bypassed",
  no_redis_io: "No Redis I/O",
  run_finished: "Run finished",
  hitl_timeout: "HITL timeout applied",
  not_completed_as_approve: "Timeout was not an approval",
};

function observedFacts(observed: Record<string, unknown> | undefined): { label: string; value: string }[] {
  if (!observed) return [];
  const rows: { label: string; value: string }[] = [];
  const add = (label: string, key: string) => {
    const v = observed[key];
    if (v === undefined || v === null || v === "") return;
    rows.push({ label, value: String(v) });
  };
  add("Terminal state", "terminal_state");
  add("Abstention reason", "abstention_reason");
  add("HITL status", "hitl_status");
  add("Graph run_id", "run_id");
  add("Subject id", "batch_id");
  if (observed.domain_payload_present === true) {
    rows.push({ label: "Deterministic findings", value: "present" });
  } else if (observed.domain_payload_present === false) {
    rows.push({ label: "Deterministic findings", value: "missing" });
  }
  if (typeof observed.cache_get_calls === "number") {
    rows.push({ label: "Cache get calls", value: String(observed.cache_get_calls) });
  }
  if (typeof observed.cache_set_calls === "number") {
    rows.push({ label: "Cache set calls", value: String(observed.cache_set_calls) });
  }
  if (observed.cache_bypassed === true) {
    rows.push({ label: "Redis", value: "bypassed (no real I/O)" });
  }
  return rows;
}

function posture(runnable: ChaosDrillExperiment[]): {
  label: string;
  tone: "ok" | "pending" | "blocked" | "neutral";
} {
  if (runnable.length === 0) return { label: "—", tone: "neutral" };
  const withResult = runnable.filter((e) => e.last_result);
  if (withResult.length === 0) return { label: "Not run", tone: "pending" };
  const failed = withResult.filter((e) => !e.last_result!.passed).length;
  if (failed > 0) return { label: `${failed} failed`, tone: "blocked" };
  if (withResult.length < runnable.length) {
    return { label: `${withResult.length} of ${runnable.length} verified`, tone: "pending" };
  }
  return { label: "All last runs passed", tone: "ok" };
}

/**
 * Chaos Drill — lab-safe ADR-007 failure injectors.
 *
 * Distinct from System Health (live probes). Each Run exercises one injectable fault on a
 * fresh graph; it does not take down Neo4j, Redis, or the API.
 */
export default function ChaosDrillPage() {
  const { session } = useAuth();
  const catalog = useApiResource((s) => getChaosDrillExperiments(s), []);
  const history = useApiResource((s) => getChaosDrillHistory(20, s), []);
  const [tab, setTab] = useState<Tab>("drills");
  const [runningId, setRunningId] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<ChaosDrillResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const resultRef = useRef<HTMLElement | null>(null);

  const canRun = catalog.data?.capabilities.can_run ?? false;
  const runnable = catalog.data?.experiments.filter((e) => e.ui_runnable) ?? [];
  const opsOnly = catalog.data?.experiments.filter((e) => !e.ui_runnable) ?? [];
  const summary = posture(runnable);
  const latestStamp = runnable
    .map((e) => e.last_result?.run_at)
    .filter((v): v is string => Boolean(v))
    .sort()
    .at(-1);

  async function onRun(experiment: ChaosDrillExperiment) {
    setRunningId(experiment.id);
    setRunError(null);
    setTab("drills");
    try {
      const result = await runChaosDrillExperiment(experiment.id);
      setLastResult(result);
      catalog.refresh();
      history.refresh();
      requestAnimationFrame(() => {
        resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    } catch (err) {
      const message =
        err instanceof ApiError ? err.userMessage : "The drill could not be completed.";
      setRunError(message);
    } finally {
      setRunningId(null);
    }
  }

  return (
    <>
      <PageHeader
        title="Chaos Drill"
        description="Named fail-closed injectors for degraded-mode claims. Each run forces a single failure on a fresh graph and records what the system actually did. Shared Neo4j, Redis, and API processes are not taken down."
        actions={
          <Button
            variant="secondary"
            onClick={() => {
              catalog.refresh();
              history.refresh();
            }}
            loading={catalog.loading || history.loading}
          >
            Refresh
          </Button>
        }
      />

      <PageBody className="space-y-6">
        {catalog.error ? (
          <ErrorState
            message={catalog.error.userMessage}
            action={<Button onClick={catalog.refresh}>Try again</Button>}
          />
        ) : !catalog.data ? (
          <Card>
            <SkeletonRows rows={5} />
          </Card>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <StatTile label="Lab drills" value={runnable.length} sub="Executable from this page" />
              <StatTile
                label="Last posture"
                value={summary.label}
                tone={summary.tone}
                sub={latestStamp ? `Latest ${formatDateTime(latestStamp)}` : "No lab drill has been run yet"}
              />
              <StatTile
                label="Recorded runs"
                value={history.data ? history.data.length : null}
                sub="Most recent 20 in chaos_drill_run"
                unavailableReason="History has not loaded yet."
              />
            </div>

            {!canRun && session && (
              <Notice tone="info" title="Run is restricted">
                Only the CISO / DPO role can start a drill. You are signed in as {session.role}.
                Catalog, last outcomes, and history remain visible.
              </Notice>
            )}

            {runError && <ErrorState message={runError} />}

            {lastResult && (
              <section ref={resultRef} aria-labelledby="chaos-latest-result">
                <ResultCard result={lastResult} />
              </section>
            )}

            <Tabs<Tab>
              label="Chaos drill sections"
              value={tab}
              onChange={setTab}
              tabs={[
                { value: "drills", label: "Lab drills", count: runnable.length },
                { value: "history", label: "History", count: history.data?.length },
                { value: "runbooks", label: "Ops runbooks", count: opsOnly.length },
              ]}
            >
              {tab === "drills" && (
                <Card>
                  <CardHeader
                    title="Lab drills"
                    description={
                      canRun
                        ? "One injector at a time. Results are stored separately from governed run history."
                        : "Read-only for this role. Sign in as CISO / DPO to run."
                    }
                  />
                  <CardBody padded={false}>
                    <ul className="divide-y divide-[var(--border-subtle)]">
                      {runnable.map((exp) => (
                        <li
                          key={exp.id}
                          className="flex flex-wrap items-start justify-between gap-3 px-4 py-4 sm:px-5"
                        >
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="font-mono text-[12px] text-[var(--text-tertiary)]">{exp.id}</p>
                              {exp.last_result ? (
                                <Badge tone={exp.last_result.passed ? "ok" : "blocked"}>
                                  {exp.last_result.overall_verdict}
                                </Badge>
                              ) : (
                                <Badge tone="neutral">Not run</Badge>
                              )}
                            </div>
                            <p className="mt-1 text-[13px] font-medium text-[var(--text-primary)]">
                              {exp.title}
                            </p>
                            <p className="mt-1 text-[12px] text-[var(--text-secondary)]">{exp.adr_row}</p>
                            {exp.last_result?.outcome_summary && (
                              <p className="mt-2 line-clamp-2 text-[12px] leading-relaxed text-[var(--text-secondary)]">
                                {exp.last_result.outcome_summary}
                              </p>
                            )}
                            {exp.last_result && (
                              <p className="mt-1.5 text-[11px] text-[var(--text-tertiary)]">
                                {formatDateTime(exp.last_result.run_at)} ·{" "}
                                {formatNumber(exp.last_result.duration_ms)} ms
                              </p>
                            )}
                          </div>
                          {canRun && (
                            <Button
                              size="sm"
                              onClick={() => onRun(exp)}
                              loading={runningId === exp.id}
                              loadingLabel="Running…"
                              disabled={runningId !== null && runningId !== exp.id}
                            >
                              Run
                            </Button>
                          )}
                        </li>
                      ))}
                    </ul>
                  </CardBody>
                </Card>
              )}

              {tab === "history" && (
                <Card>
                  <CardHeader
                    title="Drill history"
                    description="Stored in chaos_drill_run. These rows are not governed AgentRun records and do not appear on Run History."
                  />
                  <CardBody padded={false}>
                    {history.error ? (
                      <div className="p-4">
                        <ErrorState
                          message={history.error.userMessage}
                          action={<Button onClick={history.refresh}>Try again</Button>}
                        />
                      </div>
                    ) : !history.data ? (
                      <div className="p-4">
                        <SkeletonText lines={4} />
                      </div>
                    ) : history.data.length === 0 ? (
                      <EmptyState
                        title="No drills recorded"
                        description="Run a lab drill to persist an outcome. History is how this page proves a claim was actually exercised, not only documented."
                      />
                    ) : (
                      <ul className="divide-y divide-[var(--border-subtle)]">
                        {history.data.map((row) => (
                          <li
                            key={row.drill_id}
                            className="flex flex-wrap items-start justify-between gap-2 px-4 py-3.5 sm:px-5"
                          >
                            <div className="min-w-0 flex-1 pr-3">
                              <p className="font-mono text-[12px] text-[var(--text-primary)]">
                                {row.experiment_id}
                              </p>
                              <p className="mt-0.5 text-[11px] text-[var(--text-tertiary)]">
                                {formatDateTime(row.run_at)} · {row.run_by_display_name} ({row.run_by_role}) ·{" "}
                                {formatNumber(row.duration_ms)} ms
                              </p>
                              {row.outcome_summary && (
                                <p className="mt-1.5 text-[12px] leading-relaxed text-[var(--text-secondary)]">
                                  {row.outcome_summary}
                                </p>
                              )}
                            </div>
                            <Badge tone={row.passed ? "ok" : "blocked"}>{row.overall_verdict}</Badge>
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardBody>
                </Card>
              )}

              {tab === "runbooks" && (
                <Card>
                  <CardHeader
                    title="Ops runbooks"
                    description="These require a live outage or process restart. They are not executable from the browser."
                  />
                  <CardBody padded={false}>
                    <ul className="divide-y divide-[var(--border-subtle)]">
                      {opsOnly.map((exp) => (
                        <li key={exp.id} className="px-4 py-4 sm:px-5">
                          <p className="font-mono text-[12px] text-[var(--text-tertiary)]">{exp.id}</p>
                          <p className="mt-1 text-[13px] font-medium text-[var(--text-primary)]">{exp.title}</p>
                          <p className="mt-1 text-[12px] text-[var(--text-secondary)]">{exp.adr_row}</p>
                          {exp.runbook && (
                            <p className="mt-2 font-mono text-[11px] text-[var(--text-tertiary)]">{exp.runbook}</p>
                          )}
                        </li>
                      ))}
                    </ul>
                  </CardBody>
                </Card>
              )}
            </Tabs>
          </>
        )}
      </PageBody>
    </>
  );
}

function ResultCard({ result }: { result: ChaosDrillResult }) {
  const facts = observedFacts(result.observed);
  return (
    <Card>
      <CardHeader
        title="Latest result"
        description={`${result.experiment_id} · ${result.drill_id} · ${formatNumber(result.duration_ms)} ms`}
        actions={
          <Badge tone={result.passed ? "ok" : "blocked"}>
            {result.passed ? "Pass" : "Fail"}
          </Badge>
        }
      />
      <CardBody className="space-y-5">
        {result.outcome_summary && (
          <p className="text-[13px] leading-relaxed text-[var(--text-primary)]">{result.outcome_summary}</p>
        )}
        {facts.length > 0 && (
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {facts.map((fact) => (
              <Field key={fact.label} label={fact.label} mono>
                {fact.value}
              </Field>
            ))}
          </dl>
        )}
        <div>
          <p className="mb-2 text-[11px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
            Assertions
          </p>
          <ul className="divide-y divide-[var(--border-subtle)] rounded-[var(--radius-md)] border border-[var(--border-subtle)]">
            {result.assertions.map((a) => (
              <li key={a.name} className="flex flex-wrap items-start justify-between gap-2 px-3 py-2.5">
                <div className="min-w-0">
                  <p className="text-[13px] font-medium text-[var(--text-primary)]">
                    {ASSERTION_LABELS[a.name] ?? humanize(a.name)}
                  </p>
                  <p className="mt-0.5 text-[12px] text-[var(--text-secondary)]">{a.detail}</p>
                </div>
                <Badge tone={a.passed ? "ok" : "blocked"}>{a.passed ? "pass" : "fail"}</Badge>
              </li>
            ))}
          </ul>
        </div>
      </CardBody>
    </Card>
  );
}
