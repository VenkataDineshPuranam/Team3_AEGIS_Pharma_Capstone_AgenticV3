"use client";

import { useMemo, useState } from "react";
import { PageBody, PageHeader } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { SearchInput, SegmentedControl, Select } from "@/components/ui/Form";
import { EmptyState, ErrorState, Notice, SkeletonRows } from "@/components/ui/States";
import { EvidenceCard, EvidenceLegend } from "@/components/evidence/EvidenceCard";
import { StatTile } from "@/components/dashboard/StatTile";
import { useApiResource } from "@/hooks/useApiResource";
import { getEvidence, getEvidenceStats } from "@/lib/api";
import { evidenceAuthority, formatNumber, humanize } from "@/lib/format";

type Filter = "all" | "citable" | "not_citable";

/**
 * Evidence Explorer.
 *
 * Deliberately shows the whole corpus, including items no run can cite. The page's value
 * is in answering "can I rely on this?" — which requires being able to look up a document
 * and be told no. Showing an untrusted item here does not make it citable: this is a
 * read-only catalog view, and no graph reads from it.
 */
export default function EvidencePage() {
  const evidence = useApiResource((s) => getEvidence(s), []);
  const stats = useApiResource((s) => getEvidenceStats(s), []);

  const [filter, setFilter] = useState<Filter>("all");
  const [search, setSearch] = useState("");
  const [authority, setAuthority] = useState("all");

  const items = useMemo(() => evidence.data ?? [], [evidence.data]);

  const authorities = useMemo(
    () => [...new Set(items.map((i) => i.authority).filter(Boolean))].sort() as string[],
    [items],
  );

  const visible = useMemo(() => {
    let result = items;
    if (filter === "citable") result = result.filter((i) => i.citable);
    if (filter === "not_citable") result = result.filter((i) => !i.citable);
    if (authority !== "all") result = result.filter((i) => i.authority === authority);
    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(
        (i) =>
          i.evidence_id.toLowerCase().includes(q) ||
          i.source.toLowerCase().includes(q) ||
          (i.authority ?? "").toLowerCase().includes(q),
      );
    }
    // Non-citable first: the items a reviewer most needs to notice should not be buried
    // at the bottom of a list of thirty approved documents.
    return [...result].sort((a, b) => {
      if (a.citable !== b.citable) return a.citable ? 1 : -1;
      return a.evidence_id.localeCompare(b.evidence_id);
    });
  }, [items, filter, search, authority]);

  const nonCitable = items.filter((i) => !i.citable).length;

  return (
    <>
      <PageHeader
        title="Evidence"
        description="The knowledge-graph corpus that governed runs retrieve from. Every item is labelled with whether it may be relied upon — including the ones that may not."
      />

      <PageBody className="space-y-5">
        {evidence.error ? (
          <ErrorState
            title={
              evidence.error.status === 503
                ? "The knowledge graph is unreachable"
                : "Could not load the evidence corpus"
            }
            message={evidence.error.userMessage}
            hint={
              evidence.error.status === 503
                ? "Neo4j backs evidence retrieval. While it is unreachable, every workflow will abstain with dependency_unavailable rather than proceed without evidence."
                : undefined
            }
            action={<Button onClick={evidence.refresh}>Try again</Button>}
          />
        ) : (
          <>
            {/* --- corpus summary ------------------------------------- */}
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatTile label="Documents" value={formatNumber(stats.data?.total) ?? null} />
              <StatTile
                label="Citable"
                value={formatNumber(stats.data?.citable_total) ?? null}
                tone="ok"
                sub="Retrievable by a run"
              />
              <StatTile
                label="Not citable"
                value={
                  stats.data ? formatNumber(stats.data.total - stats.data.citable_total) : null
                }
                tone="blocked"
                sub="Excluded server-side"
              />
              <StatTile
                label="Supersession links"
                value={formatNumber(stats.data?.supersedes_edges) ?? null}
                sub="Document → replaced document"
              />
            </div>

            <Card>
              <CardHeader
                title="How to read these states"
                description="The four authority states are deliberately not visually equivalent."
              />
              <CardBody>
                <EvidenceLegend />
                <Notice tone="info" className="mt-4" title="Why non-citable items are shown here">
                  A run can never retrieve an untrusted or superseded document — that filter
                  lives inside the retrieval query, not in this interface. They appear in this
                  catalog so that a reviewer looking one up is told plainly that it cannot be
                  relied upon, rather than finding nothing and assuming it does not exist.
                </Notice>
              </CardBody>
            </Card>

            {/* --- toolbar -------------------------------------------- */}
            <div className="flex flex-wrap items-center gap-2">
              <SegmentedControl<Filter>
                label="Filter by citability"
                value={filter}
                onChange={setFilter}
                options={[
                  { value: "all", label: "All", count: items.length },
                  {
                    value: "citable",
                    label: "Citable",
                    count: items.length - nonCitable,
                  },
                  { value: "not_citable", label: "Not citable", count: nonCitable },
                ]}
              />
              <SearchInput
                label="Search evidence"
                value={search}
                onChange={setSearch}
                placeholder="Document id, filename or authority…"
                className="min-w-52 flex-1"
              />
              {authorities.length > 1 && (
                <Select
                  label="Authority"
                  hideLabel
                  value={authority}
                  onChange={(e) => setAuthority(e.target.value)}
                  className="w-auto min-w-44"
                >
                  <option value="all">All authorities</option>
                  {authorities.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </Select>
              )}
            </div>

            {/* --- list ------------------------------------------------ */}
            {evidence.loading && items.length === 0 ? (
              <Card>
                <SkeletonRows rows={6} />
              </Card>
            ) : visible.length === 0 ? (
              <Card>
                <EmptyState
                  title="No documents match"
                  description={
                    items.length === 0
                      ? "The knowledge graph holds no evidence nodes. Seed the corpus with `python -m packages.domain.kg.ingest`."
                      : `The corpus holds ${items.length} documents, but none match the current filters.`
                  }
                  action={
                    items.length > 0 ? (
                      <Button
                        onClick={() => {
                          setFilter("all");
                          setSearch("");
                          setAuthority("all");
                        }}
                      >
                        Clear filters
                      </Button>
                    ) : undefined
                  }
                />
              </Card>
            ) : (
              <>
                <p className="text-[13px] text-[var(--text-tertiary)]">
                  Showing <span className="tnum font-medium">{visible.length}</span> of{" "}
                  <span className="tnum">{items.length}</span> documents
                </p>
                <ul className="space-y-2">
                  {visible.map((item) => (
                    <li key={item.evidence_id}>
                      <EvidenceCard item={item} />
                    </li>
                  ))}
                </ul>
              </>
            )}

            {/* --- status breakdown ------------------------------------ */}
            {stats.data && (
              <Card>
                <CardHeader title="Corpus by raw status" level={3} />
                <CardBody>
                  <dl className="flex flex-wrap gap-x-6 gap-y-2">
                    {Object.entries(stats.data.by_status).map(([status, count]) => {
                      const auth = evidenceAuthority(
                        status,
                        items.find((i) => i.status === status)?.citable ?? false,
                      );
                      return (
                        <div key={status} className="flex items-baseline gap-2">
                          <dt className="text-[13px] text-[var(--text-secondary)]">
                            {humanize(status)}
                          </dt>
                          <dd className="tnum text-[13px] font-medium text-[var(--text-primary)]">
                            {count}
                          </dd>
                          <span className="text-[11px] text-[var(--text-tertiary)]">→ {auth}</span>
                        </div>
                      );
                    })}
                  </dl>
                  <p className="mt-3 text-[11px] leading-relaxed text-[var(--text-tertiary)]">
                    Citability is reported by the backend from the same rule the retrieval tool
                    enforces, not re-derived here. Note that <code className="font-mono">local_approved</code>{" "}
                    reads as approved but is outside that rule&apos;s citable set, so it is
                    correctly shown as not citable.
                  </p>
                </CardBody>
              </Card>
            )}
          </>
        )}
      </PageBody>
    </>
  );
}
