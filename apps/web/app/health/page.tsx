"use client";

import { PageBody, PageHeader } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ErrorState, SkeletonRows } from "@/components/ui/States";
import { toneForDependency } from "@/components/domain/Chips";
import { Badge } from "@/components/ui/Badge";
import { useApiResource, useVisiblePolling } from "@/hooks/useApiResource";
import { getHealthDetail } from "@/lib/api";
import { formatDateTime, formatNumber, humanize } from "@/lib/format";

/**
 * System Health.
 *
 * Every status here is the result of the backend actually touching the dependency
 * (services/api/health_probe.py) — not a config check dressed up as a health check. The
 * LLM provider is the one exception, and its card says so: a live call on every page load
 * would spend real tokens, which is exactly what the denial-of-wallet ceiling exists to
 * prevent.
 */
export default function HealthPage() {
  const pollMs = useVisiblePolling(30_000);
  const health = useApiResource((s) => getHealthDetail(s), [], { pollMs });

  return (
    <>
      <PageHeader
        title="System Health"
        description="Measured dependency status. Each entry is the result of an actual probe run at the time shown — not an inference from configuration."
      />

      <PageBody className="space-y-5">
        {health.error ? (
          <ErrorState
            message={health.error.userMessage}
            action={<Button onClick={health.refresh}>Try again</Button>}
          />
        ) : !health.data ? (
          <Card>
            <SkeletonRows rows={5} />
          </Card>
        ) : (
          <>
            <p className="text-[12px] text-[var(--text-tertiary)]">
              Checked {formatDateTime(health.data.checked_at)}
            </p>

            <Card>
              <CardHeader title="Orchestrator API" />
              <CardBody className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[13px] text-[var(--text-primary)]">{health.data.api.detail}</p>
                </div>
                <Badge tone={toneForDependency(health.data.api.status)}>
                  {humanize(health.data.api.status)}
                </Badge>
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Dependencies"
                description="Four distinct states, so a missing credential and a genuine outage are never shown the same way."
              />
              <CardBody padded={false}>
                <ul className="divide-y divide-[var(--border-subtle)]">
                  {health.data.dependencies.map((dep) => (
                    <li key={dep.name} className="flex flex-wrap items-start justify-between gap-3 px-4 py-3.5 sm:px-5">
                      <div className="min-w-0">
                        <p className="text-[13px] font-medium text-[var(--text-primary)]">{dep.name}</p>
                        {dep.detail && (
                          <p className="mt-0.5 text-[12px] text-[var(--text-secondary)]">{dep.detail}</p>
                        )}
                      </div>
                      <div className="flex shrink-0 items-center gap-3">
                        {dep.latency_ms != null && (
                          <span className="tnum text-[11px] text-[var(--text-tertiary)]">
                            {dep.latency_ms}ms
                          </span>
                        )}
                        <Badge tone={toneForDependency(dep.status)}>{humanize(dep.status)}</Badge>
                      </div>
                    </li>
                  ))}
                </ul>
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Audit store" description={health.data.audit_store.db_path} />
              <CardBody>
                <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                  {Object.entries(health.data.audit_store.row_counts).map(([table, count]) => (
                    <div key={table} className="rounded-[var(--radius-md)] bg-[var(--surface-sunken)] px-3 py-2.5">
                      <dt className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
                        {humanize(table)}
                      </dt>
                      <dd className="tnum mt-0.5 text-lg font-semibold text-[var(--text-primary)]">
                        {formatNumber(count)}
                      </dd>
                    </div>
                  ))}
                </dl>
                <p className="mt-3 text-[12px] text-[var(--text-tertiary)]">
                  Latest run recorded {formatDateTime(health.data.audit_store.latest_run_recorded_at)}
                </p>
              </CardBody>
            </Card>
          </>
        )}
      </PageBody>
    </>
  );
}
