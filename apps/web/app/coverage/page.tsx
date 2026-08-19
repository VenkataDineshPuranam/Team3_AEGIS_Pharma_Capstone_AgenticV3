"use client";

import { useMemo, useState } from "react";
import { PageBody, PageHeader } from "@/components/layout/AppShell";
import { RequireRole } from "@/components/layout/RequireRole";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { SearchInput, Select } from "@/components/ui/Form";
import { EmptyState, ErrorState, Notice, SkeletonText } from "@/components/ui/States";
import { Tabs } from "@/components/ui/Tabs";
import { StatTile } from "@/components/dashboard/StatTile";
import { StatusBar } from "@/components/coverage/StatusBar";
import { InjectRow } from "@/components/coverage/InjectRow";
import { useApiResource } from "@/hooks/useApiResource";
import { getEvalScorecard, getInjectCoverage, type CoverageStatus } from "@/lib/api";
import {
  COVERAGE_STATUS_LABELS,
  COVERAGE_STATUS_MEANING,
  COVERAGE_STATUS_ORDER,
  COVERAGE_STATUS_TONE,
  humanizeCategory,
} from "@/lib/coverage-format";
import { formatPercent } from "@/lib/format";

type Tab = "injects" | "evals";
type StatusFilter = CoverageStatus | "all";

/**
 * Evaluation & Security Coverage.
 *
 * Two genuinely different data sources, kept in two tabs rather than blended into one
 * fake score (see services/api/eval_dashboard.py's module docstring for the full
 * reasoning):
 *
 *   - Eval Harness: the real eval-ai-cache scenario suite, executed LIVE on every load of
 *     this page (~25ms, pure grading logic, no LLM/network calls) -- these numbers can
 *     differ from five minutes ago if the grader code changed.
 *   - Domain & Security Coverage: a curated mapping of the 84 tabletop-exercise "injects"
 *     inherited from the predecessor V1 project against what V2's actual codebase does
 *     today. This is read from a reviewed file, not recomputed per request -- determining
 *     whether a scenario is genuinely addressed requires understanding code, not a script.
 */
export default function CoveragePage() {
  return (
    <RequireRole role="Super Admin">
      <CoverageDashboard />
    </RequireRole>
  );
}

function CoverageDashboard() {
  const [tab, setTab] = useState<Tab>("injects");
  const injects = useApiResource((s) => getInjectCoverage(s), []);
  const evals = useApiResource((s) => getEvalScorecard(s), []);

  const injectAddressed =
    injects.data ? (injects.data.by_status.COVERED ?? 0) + (injects.data.by_status.PARTIAL ?? 0) : null;
  const injectInScope = injects.data ? injects.data.total_injects - (injects.data.by_status.OUT_OF_SCOPE ?? 0) : null;
  const injectGaps = injects.data?.by_status.NOT_COVERED ?? null;

  return (
    <>
      <PageHeader
        title="Evaluation & Security Coverage"
        description="System-wide verification posture, visible only to Super Admin. Every status below cites a real file — nothing here is an estimate."
      />
      <PageBody className="space-y-6">
        {/* --- system posture: one row combining both data sources -------- */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile
            label="Eval pass rate"
            value={evals.data ? formatPercent(evals.data.total_scenarios ? evals.data.passed / evals.data.total_scenarios : 0) : null}
            tone={evals.data && evals.data.failed > 0 ? "blocked" : "ok"}
            sub={evals.data ? `${evals.data.passed} / ${evals.data.total_scenarios} scenarios, executed live` : undefined}
            unavailableReason="The eval harness could not be reached."
          />
          <StatTile
            label="Inject coverage"
            value={injectInScope != null && injectAddressed != null ? formatPercent(injectInScope ? injectAddressed / injectInScope : 0) : null}
            tone="ok"
            sub={injectInScope != null ? `${injectAddressed} / ${injectInScope} in-scope scenarios addressed` : undefined}
            unavailableReason="Coverage data could not be reached."
          />
          <StatTile
            label="Open eval failures"
            value={evals.data?.failed ?? null}
            tone={evals.data && evals.data.failed > 0 ? "blocked" : "neutral"}
            sub="From the live harness run above"
            unavailableReason="The eval harness could not be reached."
          />
          <StatTile
            label="Open coverage gaps"
            value={injectGaps}
            tone={injectGaps ? "blocked" : "neutral"}
            sub="In scope, nothing addresses it yet"
            unavailableReason="Coverage data could not be reached."
          />
        </div>

        <Tabs<Tab>
          label="Coverage sections"
          value={tab}
          onChange={setTab}
          tabs={[
            { value: "injects", label: "Domain & Security Coverage", count: injects.data?.total_injects },
            { value: "evals", label: "Eval Harness", count: evals.data?.total_scenarios },
          ]}
        >
          {tab === "injects" && <InjectsTab />}
          {tab === "evals" && <EvalsTab />}
        </Tabs>
      </PageBody>
    </>
  );

  function InjectsTab() {
    if (injects.error) {
      return (
        <ErrorState
          message={injects.error.userMessage}
          action={<Button onClick={injects.refresh}>Try again</Button>}
        />
      );
    }
    if (!injects.data) {
      return (
        <Card>
          <CardBody>
            <SkeletonText lines={8} />
          </CardBody>
        </Card>
      );
    }
    return <InjectsContent data={injects.data} />;
  }

  function EvalsTab() {
    if (evals.error) {
      return (
        <ErrorState message={evals.error.userMessage} action={<Button onClick={evals.refresh}>Try again</Button>} />
      );
    }
    if (!evals.data) {
      return (
        <Card>
          <CardBody>
            <SkeletonText lines={8} />
          </CardBody>
        </Card>
      );
    }
    return <EvalsContent data={evals.data} />;
  }
}

function InjectsContent({ data }: { data: NonNullable<ReturnType<typeof useApiResource<Awaited<ReturnType<typeof getInjectCoverage>>>>["data"]> }) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [dimensionFilter, setDimensionFilter] = useState("all");
  const [search, setSearch] = useState("");

  const inScope = data.total_injects - (data.by_status.OUT_OF_SCOPE ?? 0);
  const addressed = (data.by_status.COVERED ?? 0) + (data.by_status.PARTIAL ?? 0);

  const filtered = useMemo(() => {
    let items = data.injects;
    if (statusFilter !== "all") items = items.filter((i) => i.status === statusFilter);
    if (dimensionFilter !== "all") items = items.filter((i) => i.dimension === dimensionFilter);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      items = items.filter(
        (i) =>
          i.id.toLowerCase().includes(q) ||
          i.title.toLowerCase().includes(q) ||
          i.scenario.toLowerCase().includes(q) ||
          i.rationale.toLowerCase().includes(q),
      );
    }
    return items;
  }, [data.injects, statusFilter, dimensionFilter, search]);

  const byDimension = useMemo(() => {
    const groups = new Map<string, typeof filtered>();
    for (const item of filtered) {
      groups.set(item.dimension, [...(groups.get(item.dimension) ?? []), item]);
    }
    return groups;
  }, [filtered]);

  return (
    <div className="space-y-6">
      <Notice tone="info" title="Where this dataset comes from">
        {data.methodology}
      </Notice>

      {/* --- summary ---------------------------------------------------- */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Total scenarios" value={data.total_injects} sub="13 dimensions, from the V1 tabletop exercise" />
        <StatTile
          label="In scope for V2"
          value={inScope}
          sub={`${data.by_status.OUT_OF_SCOPE ?? 0} fall outside what V2 builds`}
        />
        <StatTile
          label="Addressed"
          value={`${addressed} / ${inScope}`}
          tone="ok"
          sub={formatPercent(inScope ? addressed / inScope : 0) + " of in-scope scenarios"}
        />
        <StatTile
          label="Real gaps"
          value={data.by_status.NOT_COVERED ?? 0}
          tone={data.by_status.NOT_COVERED ? "blocked" : "neutral"}
          sub="In scope, nothing addresses it yet"
        />
      </div>

      {/* --- legend ------------------------------------------------------ */}
      <div className="flex flex-wrap gap-x-5 gap-y-2 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--surface-sunken)] px-3.5 py-3">
        {COVERAGE_STATUS_ORDER.map((status) => (
          <div key={status} className="flex items-center gap-2">
            <Badge tone={COVERAGE_STATUS_TONE[status]} size="xs">
              {COVERAGE_STATUS_LABELS[status]}
            </Badge>
            <span className="text-[11px] text-[var(--text-tertiary)]">{COVERAGE_STATUS_MEANING[status]}</span>
          </div>
        ))}
      </div>

      {/* --- dimension matrix -------------------------------------------- */}
      <Card>
        <CardHeader
          title="Coverage by dimension"
          description="13 risk dimensions from the V1 exercise, each with its own release-gate framing"
        />
        <CardBody className="space-y-3">
          {data.dimensions.map((dim) => (
            <button
              key={dim.id}
              type="button"
              onClick={() => setDimensionFilter(dim.id === dimensionFilter ? "all" : dim.id)}
              className={`block w-full rounded-[var(--radius-md)] border px-3 py-2.5 text-left transition-colors ${
                dimensionFilter === dim.id
                  ? "border-[var(--brand)] bg-[var(--brand-subtle)]"
                  : "border-[var(--border-subtle)] hover:bg-[var(--surface-sunken)]"
              }`}
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="text-[13px] font-medium text-[var(--text-primary)]">
                  <span className="font-mono text-[11px] text-[var(--text-tertiary)]">{dim.id}</span>{" "}
                  {dim.title}
                </span>
                <span className="text-[11px] text-[var(--text-tertiary)]">
                  {dim.inject_count} scenarios · {dim.release_gate}
                </span>
              </div>
              <StatusBar counts={dim.by_status} total={dim.inject_count} height="h-2" />
            </button>
          ))}
        </CardBody>
      </Card>

      {/* --- toolbar ------------------------------------------------------ */}
      <div className="flex flex-wrap items-center gap-2">
        <SearchInput
          label="Search scenarios"
          value={search}
          onChange={setSearch}
          placeholder="Inject id, title, or rationale…"
          className="min-w-56 flex-1"
        />
        <Select
          label="Status"
          hideLabel
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
          className="w-auto min-w-40"
        >
          <option value="all">All statuses</option>
          {COVERAGE_STATUS_ORDER.map((s) => (
            <option key={s} value={s}>
              {COVERAGE_STATUS_LABELS[s]} ({data.by_status[s] ?? 0})
            </option>
          ))}
        </Select>
        <Select
          label="Dimension"
          hideLabel
          value={dimensionFilter}
          onChange={(e) => setDimensionFilter(e.target.value)}
          className="w-auto min-w-32"
        >
          <option value="all">All dimensions</option>
          {data.dimensions.map((d) => (
            <option key={d.id} value={d.id}>
              {d.id}
            </option>
          ))}
        </Select>
        {(statusFilter !== "all" || dimensionFilter !== "all" || search) && (
          <Button
            variant="ghost"
            onClick={() => {
              setStatusFilter("all");
              setDimensionFilter("all");
              setSearch("");
            }}
          >
            Clear
          </Button>
        )}
      </div>

      {/* --- list ----------------------------------------------------------- */}
      {filtered.length === 0 ? (
        <Card>
          <EmptyState title="No scenarios match" description="Try a broader filter or clear the search." />
        </Card>
      ) : (
        <div className="space-y-5">
          {[...byDimension.entries()].map(([dimId, items]) => {
            const dim = data.dimensions.find((d) => d.id === dimId)!;
            return (
              <div key={dimId}>
                <h3 className="mb-2 flex items-baseline gap-2 text-[12px] font-semibold text-[var(--text-secondary)]">
                  <span className="font-mono text-[var(--text-tertiary)]">{dimId}</span>
                  {dim.title}
                  <span className="font-normal text-[var(--text-tertiary)]">({items.length})</span>
                </h3>
                <ul className="space-y-1.5">
                  {items.map((inject) => (
                    <InjectRow key={inject.id} inject={inject} />
                  ))}
                </ul>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function EvalsContent({ data }: { data: NonNullable<ReturnType<typeof useApiResource<Awaited<ReturnType<typeof getEvalScorecard>>>>["data"]> }) {
  return (
    <div className="space-y-6">
      <Notice tone="ok" title="Executed live, this page load">
        {data.source}
      </Notice>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Scenarios" value={data.total_scenarios} sub={`${data.category_count} categories`} />
        <StatTile
          label="Passed"
          value={data.passed}
          tone="ok"
          sub={formatPercent(data.total_scenarios ? data.passed / data.total_scenarios : 0)}
        />
        <StatTile
          label="Failed"
          value={data.failed}
          tone={data.failed > 0 ? "blocked" : "neutral"}
          sub={data.failed === 0 ? "Zero failures" : "Needs attention"}
        />
        <StatTile
          label="Accepted non-pass"
          value={data.accepted_non_pass}
          sub="human_rubric / blocked-by-environment / threshold-not-defined"
        />
      </div>

      <div className="space-y-3">
        {data.categories.map((cat) => (
          <Card key={cat.category}>
            <CardHeader
              level={3}
              title={humanizeCategory(cat.category)}
              description={`${cat.scenario_count} scenarios`}
              actions={
                <div className="flex items-center gap-2">
                  {cat.passed > 0 && (
                    <Badge tone="ok" size="xs">
                      {cat.passed} pass
                    </Badge>
                  )}
                  {cat.failed > 0 && (
                    <Badge tone="blocked" size="xs">
                      {cat.failed} fail
                    </Badge>
                  )}
                  {cat.non_pass_accepted > 0 && (
                    <Badge tone="neutral" size="xs">
                      {cat.non_pass_accepted} other
                    </Badge>
                  )}
                </div>
              }
            />
            <CardBody padded={false}>
              <ul className="divide-y divide-[var(--border-subtle)]">
                {cat.scenarios.map((s) => (
                  <li key={s.scenario_id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2 sm:px-5">
                    <span className="font-mono text-[12px] font-medium text-[var(--text-primary)]">
                      {s.scenario_id}
                    </span>
                    <Badge
                      tone={s.outcome === "PASS" ? "ok" : s.is_failure ? "blocked" : "neutral"}
                      size="xs"
                    >
                      {s.outcome}
                    </Badge>
                    <span className="min-w-0 flex-1 truncate text-[12px] text-[var(--text-tertiary)]">
                      {s.detail}
                    </span>
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
