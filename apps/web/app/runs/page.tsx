"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageBody, PageHeader } from "@/components/layout/AppShell";
import { useAuth } from "@/components/layout/AuthContext";
import { Button } from "@/components/ui/Button";
import { Card, NotRecorded } from "@/components/ui/Card";
import { SearchInput, Select } from "@/components/ui/Form";
import { EmptyState, ErrorState, SkeletonRows } from "@/components/ui/States";
import { MobileCardList, Pagination, Table, Td, Th, Tr } from "@/components/ui/Table";
import { Identifier, StateBadge, WorkflowChip } from "@/components/domain/Chips";
import { useApiResource } from "@/hooks/useApiResource";
import { ApiError, downloadRunsExport, getRunFilters, getRunHistory } from "@/lib/api";
import { ABSTENTION_EXPLANATIONS, formatDateTime, formatNumber, humanize } from "@/lib/format";

const PAGE_SIZE = 25;

/** Mirrors services/api/main.py::_AUDIT_EXPORT_ROLES -- UI convenience only, the API is
 *  what actually enforces this (services/api/main.py::_require_audit_role). These three
 *  roles all have an empty `approver_for` in ROLE_CATALOG: a full exportable run record
 *  is the actual product surface their account exists for. */
const AUDIT_EXPORT_ROLES = ["Super Admin", "Auditor", "Unblinding authority"];

/**
 * Run History — historical investigation over the append-only audit store.
 *
 * Filtering and pagination are server-side: the store holds hundreds of runs and will
 * hold more, so loading it all to filter in the browser would not stay honest. The filter
 * options themselves come from /api/runs/filters, which reports the values actually
 * present — a hardcoded list would eventually offer a state no run has.
 */
export default function RunHistoryPage() {
  const { session } = useAuth();
  const canExport = Boolean(session && AUDIT_EXPORT_ROLES.includes(session.role));
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  async function handleExport() {
    setExporting(true);
    setExportError(null);
    try {
      await downloadRunsExport();
    } catch (e) {
      setExportError(e instanceof ApiError ? e.userMessage : "The export could not be downloaded.");
    } finally {
      setExporting(false);
    }
  }

  const [workflow, setWorkflow] = useState("");
  const [terminalState, setTerminalState] = useState("");
  const [search, setSearch] = useState("");
  const [debounced, setDebounced] = useState("");
  const [offset, setOffset] = useState(0);

  // Debounce the search so typing does not fire a request per keystroke (Phase 27).
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  // Any filter change invalidates the current page number. Adjusted during render (React's
  // recommended pattern for "reset state when an input changes") rather than in an effect,
  // so the stale page never paints even for one frame.
  const filterKey = `${workflow}|${terminalState}|${debounced}`;
  const [lastFilterKey, setLastFilterKey] = useState(filterKey);
  if (filterKey !== lastFilterKey) {
    setLastFilterKey(filterKey);
    if (offset !== 0) setOffset(0);
  }

  const filters = useApiResource((s) => getRunFilters(s), []);
  const runs = useApiResource(
    (s) =>
      getRunHistory(
        {
          workflow: workflow || undefined,
          terminal_state: terminalState || undefined,
          search: debounced || undefined,
          limit: PAGE_SIZE,
          offset,
        },
        s,
      ),
    [workflow, terminalState, debounced, offset],
  );

  const items = runs.data?.items ?? [];
  const total = runs.data?.total ?? 0;
  const hasFilters = Boolean(workflow || terminalState || debounced);

  return (
    <>
      <PageHeader
        title="Run History"
        description="Every run recorded in the append-only audit store. Records are written when a run finalizes and can never be modified or removed."
        actions={
          canExport ? (
            <Button variant="secondary" onClick={handleExport} loading={exporting}>
              Export audit report
            </Button>
          ) : undefined
        }
      />

      <PageBody className="space-y-4">
        {exportError && (
          <ErrorState message={exportError} action={<Button onClick={handleExport}>Try again</Button>} />
        )}
        <div className="flex flex-wrap items-center gap-2">
          <SearchInput
            label="Search runs"
            value={search}
            onChange={setSearch}
            placeholder="Run id or subject id…"
            className="min-w-56 flex-1"
          />
          <Select
            label="Workflow"
            hideLabel
            value={workflow}
            onChange={(e) => setWorkflow(e.target.value)}
            className="w-auto min-w-40"
          >
            <option value="">All workflows</option>
            {(filters.data?.workflow ?? []).map((w) => (
              <option key={w} value={w}>
                {humanize(w)}
              </option>
            ))}
          </Select>
          <Select
            label="Outcome"
            hideLabel
            value={terminalState}
            onChange={(e) => setTerminalState(e.target.value)}
            className="w-auto min-w-36"
          >
            <option value="">All outcomes</option>
            {(filters.data?.terminal_state ?? []).map((s) => (
              <option key={s} value={s}>
                {humanize(s)}
              </option>
            ))}
          </Select>
          {hasFilters && (
            <Button
              variant="ghost"
              onClick={() => {
                setWorkflow("");
                setTerminalState("");
                setSearch("");
              }}
            >
              Clear
            </Button>
          )}
        </div>

        {runs.error ? (
          <ErrorState
            message={runs.error.userMessage}
            action={<Button onClick={runs.refresh}>Try again</Button>}
          />
        ) : runs.loading && items.length === 0 ? (
          <Card>
            <SkeletonRows rows={8} />
          </Card>
        ) : items.length === 0 ? (
          <Card>
            <EmptyState
              title={hasFilters ? "No runs match these filters" : "No runs recorded yet"}
              description={
                hasFilters
                  ? "Try a broader workflow or outcome filter, or clear the search."
                  : "The audit store is empty. Every run writes a record here when it finalizes — including runs that abstained, were refused, or were blocked."
              }
            />
          </Card>
        ) : (
          <Card>
            {/* Desktop: table. */}
            <div className="hidden md:block">
              <Table caption="Recorded runs, newest first">
                <thead>
                  <tr>
                    <Th>Outcome</Th>
                    <Th>Workflow</Th>
                    <Th>Subject</Th>
                    <Th>Run</Th>
                    <Th>Reason</Th>
                    <Th align="right">Tokens</Th>
                    <Th align="right">Recorded</Th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((run) => (
                    <Tr key={run.run_id}>
                      <Td>
                        <Link href={`/runs/${encodeURIComponent(run.run_id)}`}>
                          <StateBadge state={run.terminal_state} size="xs" />
                        </Link>
                      </Td>
                      <Td>
                        <WorkflowChip workflow={run.workflow} size="xs" />
                      </Td>
                      <Td mono>
                        {run.subject_id ?? (
                          <span className="text-[11px]">
                            <NotRecorded reason="This run predates subject-id recording." />
                          </span>
                        )}
                      </Td>
                      <Td>
                        <Link
                          href={`/runs/${encodeURIComponent(run.run_id)}`}
                          className="font-mono text-[13px] text-[var(--brand)] hover:underline"
                        >
                          {run.run_id}
                        </Link>
                      </Td>
                      <Td>
                        {run.abstention_reason ? (
                          <span
                            className="text-[12px] text-[var(--text-secondary)]"
                            title={ABSTENTION_EXPLANATIONS[run.abstention_reason]}
                          >
                            {humanize(run.abstention_reason)}
                          </span>
                        ) : (
                          <span className="text-[var(--text-tertiary)]">—</span>
                        )}
                      </Td>
                      <Td align="right" mono>
                        {run.tokens_in != null
                          ? formatNumber((run.tokens_in ?? 0) + (run.tokens_out ?? 0))
                          : "—"}
                      </Td>
                      <Td align="right" mono className="whitespace-nowrap text-[12px]">
                        {formatDateTime(run.recorded_at)}
                      </Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            </div>

            {/* Mobile: cards. */}
            <div className="md:hidden">
              <MobileCardList>
                {items.map((run) => (
                  <li key={run.run_id}>
                    <Link
                      href={`/runs/${encodeURIComponent(run.run_id)}`}
                      className="block px-4 py-3 hover:bg-[var(--surface-sunken)]"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <StateBadge state={run.terminal_state} size="xs" />
                        <WorkflowChip workflow={run.workflow} size="xs" />
                        {run.subject_id && (
                          <span className="font-mono text-[13px] font-medium">
                            {run.subject_id}
                          </span>
                        )}
                      </div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1">
                        <Identifier value={run.run_id} className="text-[11px]" />
                        {run.abstention_reason && (
                          <span className="text-[11px] text-[var(--text-tertiary)]">
                            {humanize(run.abstention_reason)}
                          </span>
                        )}
                      </div>
                      <p className="mt-1 tnum text-[11px] text-[var(--text-tertiary)]">
                        {formatDateTime(run.recorded_at)}
                      </p>
                    </Link>
                  </li>
                ))}
              </MobileCardList>
            </div>

            <Pagination offset={offset} limit={PAGE_SIZE} total={total} onChange={setOffset} />
          </Card>
        )}
      </PageBody>
    </>
  );
}
