"use client";

import { useState } from "react";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/Badge";
import type { EvidenceCatalogItem, EvidenceRef } from "@/lib/api";
import {
  EVIDENCE_AUTHORITY_MEANING,
  HUMAN_PRECEDENT_MEANING,
  evidenceAuthority,
  evidenceTone,
  isHumanPrecedent,
} from "@/lib/format";

/**
 * One evidence item.
 *
 * Phase 9's central requirement is that the four authority states must not be visually
 * equivalent. Here that is enforced structurally, not by convention: a non-citable item
 * gets a coloured left rule, a distinct badge with its own glyph, and an explicit
 * "cannot be relied upon" line. An authoritative item gets none of that treatment. The
 * two cannot be mistaken for one another at a glance, in colour or in greyscale.
 */
export function EvidenceCard({
  item,
  citedBy,
  className,
}: {
  item: EvidenceCatalogItem;
  /** Claim texts that cite this item, if shown in a finding context. */
  citedBy?: string[];
  className?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const authority = evidenceAuthority(item.status, item.citable);
  const tone = evidenceTone(authority);
  const usable = authority === "AUTHORITATIVE" || authority === "DRAFT";
  const precedent = isHumanPrecedent(item.source);

  const rule = {
    AUTHORITATIVE: "before:bg-[var(--evidence-authoritative-fg)]",
    DRAFT: "before:bg-[var(--evidence-draft-fg)]",
    UNTRUSTED: "before:bg-[var(--evidence-untrusted-fg)]",
    SUPERSEDED: "before:bg-[var(--evidence-superseded-fg)]",
    "NOT CITABLE": "before:bg-[var(--status-blocked-fg)]",
  }[authority];

  return (
    <article
      className={cn(
        "relative overflow-hidden rounded-[var(--radius-md)] border bg-[var(--surface-raised)]",
        // The left rule is the fastest signal in a long list -- readable before any text.
        "before:absolute before:inset-y-0 before:left-0 before:w-1",
        rule,
        usable ? "border-[var(--border-subtle)]" : "border-[var(--border-default)]",
        className,
      )}
    >
      <div className="py-3 pl-4 pr-3.5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[13px] font-semibold text-[var(--text-primary)]">
                {item.evidence_id}
              </span>
              <Badge tone={tone} size="xs" title={EVIDENCE_AUTHORITY_MEANING[authority]}>
                {authority}
              </Badge>
              {item.status !== "approved" && item.status !== authority.toLowerCase() && (
                <span className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
                  status: {item.status}
                </span>
              )}
            </div>
            <p className="mt-1 break-words text-[13px] text-[var(--text-secondary)]">
              {item.source}
            </p>
          </div>

          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="shrink-0 rounded-[var(--radius-sm)] px-1.5 py-0.5 text-[11px] text-[var(--text-tertiary)] hover:bg-[var(--surface-sunken)] hover:text-[var(--text-primary)]"
          >
            {expanded ? "Less" : "Details"}
            <span aria-hidden="true" className="ml-1">
              {expanded ? "▲" : "▼"}
            </span>
          </button>
        </div>

        {/* ADR-010: distinguishable from an ordinary governance document, present whether
            or not the item is usable -- a precedent is always worth flagging as what it
            is. */}
        {precedent && (
          <p className="mt-2 rounded-[var(--radius-sm)] bg-[var(--evidence-draft-bg)] px-2 py-1.5 text-[12px] font-medium text-[var(--evidence-draft-fg)]">
            {HUMAN_PRECEDENT_MEANING}
          </p>
        )}

        {/* The unmissable line. Present only when it is true. */}
        {!usable && (
          <p
            className={cn(
              "mt-2 rounded-[var(--radius-sm)] px-2 py-1.5 text-[12px] font-medium",
              authority === "SUPERSEDED"
                ? "bg-[var(--evidence-superseded-bg)] text-[var(--evidence-superseded-fg)]"
                : "bg-[var(--status-blocked-bg)] text-[var(--status-blocked-fg)]",
            )}
          >
            {EVIDENCE_AUTHORITY_MEANING[authority]}
            {item.superseded_by && (
              <>
                {" "}
                Replaced by{" "}
                <span className="font-mono font-semibold">{item.superseded_by}</span>.
              </>
            )}
          </p>
        )}

        {citedBy && citedBy.length > 0 && (
          <div className="mt-2 border-l-2 border-[var(--border-default)] pl-2.5">
            <p className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
              Supports {citedBy.length} finding{citedBy.length === 1 ? "" : "s"}
            </p>
            <ul className="mt-1 space-y-0.5">
              {citedBy.map((text, i) => (
                <li key={i} className="text-[12px] leading-snug text-[var(--text-secondary)]">
                  {text}
                </li>
              ))}
            </ul>
          </div>
        )}

        {expanded && (
          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 border-t border-[var(--border-subtle)] pt-3 text-[12px] sm:grid-cols-3">
            <Detail label="Authority" value={item.authority} />
            <Detail label="Jurisdiction" value={item.jurisdiction} />
            <Detail label="Effective" value={item.effective_date} />
            <Detail label="Supersedes" value={item.supersedes} mono />
            <Detail label="Superseded by" value={item.superseded_by} mono />
            <Detail label="Raw status" value={item.status} />
            {/* Document text is not held in the knowledge graph -- the ingest stores
                metadata and a content hash only. Saying so beats an empty panel. */}
            <div className="col-span-full">
              <dt className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
                Excerpt
              </dt>
              <dd className="mt-0.5 text-[var(--text-tertiary)] italic">
                Document text is not stored in the knowledge graph — only catalog metadata
                and a content hash. Open the source document to read it.
              </dd>
            </div>
          </dl>
        )}
      </div>
    </article>
  );
}

function Detail({
  label,
  value,
  mono,
}: {
  label: string;
  value: string | null | undefined;
  mono?: boolean;
}) {
  return (
    <div className="min-w-0">
      <dt className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">{label}</dt>
      <dd
        className={cn(
          "mt-0.5 break-words text-[var(--text-primary)]",
          mono && "font-mono text-[11px]",
        )}
      >
        {value || <span className="text-[var(--text-tertiary)] italic">—</span>}
      </dd>
    </div>
  );
}

/**
 * Compact form for evidence attached to a run.
 *
 * A run's `EvidenceRef` has passed the citable filter by construction (a non-citable item
 * cannot exist as an EvidenceItem in graph state), so this variant states that positively
 * rather than re-deriving an authority it cannot doubt.
 */
export function RunEvidenceCard({
  item,
  citedBy,
}: {
  item: EvidenceRef;
  citedBy?: string[];
}) {
  return (
    <EvidenceCard
      item={{
        evidence_id: item.evidence_id,
        source: item.source,
        status: item.status,
        // True by construction: this item was retrieved by the governed tool, which
        // filters non-citable statuses inside its own query.
        citable: true,
        authority: null,
        jurisdiction: item.jurisdiction,
        effective_date: item.effective_date,
        supersedes: item.supersedes,
        superseded_by: null,
        content_excerpt: item.content_excerpt,
      }}
      citedBy={citedBy}
    />
  );
}

export function EvidenceLegend() {
  const states = ["AUTHORITATIVE", "DRAFT", "SUPERSEDED", "UNTRUSTED", "NOT CITABLE"] as const;
  return (
    <dl className="flex flex-wrap gap-x-5 gap-y-2">
      {states.map((state) => (
        <div key={state} className="flex items-center gap-2">
          <dt>
            <Badge tone={evidenceTone(state)} size="xs">
              {state}
            </Badge>
          </dt>
          <dd className="text-[11px] text-[var(--text-tertiary)]">
            {EVIDENCE_AUTHORITY_MEANING[state]}
          </dd>
        </div>
      ))}
    </dl>
  );
}
