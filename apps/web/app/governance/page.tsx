"use client";

import { useState } from "react";
import Link from "next/link";
import { PageBody, PageHeader } from "@/components/layout/AppShell";
import { useAuth } from "@/components/layout/AuthContext";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ErrorState, Notice, SkeletonText } from "@/components/ui/States";
import { cn } from "@/lib/cn";
import { useApiResource } from "@/hooks/useApiResource";
import { getGovernance } from "@/lib/api";
import { WORKFLOW_LABELS, humanize } from "@/lib/format";

type Section = "guide" | "governance";

/**
 * Getting Started + Governance, one page in two sections.
 *
 * Previously two separate nav destinations that people kept mistaking for duplicates of
 * each other. They aren't duplicates -- Getting Started is first-five-minutes orientation
 * for a person who has never seen AEGIS before, Governance is a live enforcement
 * reference sourced from the code that actually enforces each rule (see
 * services/api/governance_view.py's module docstring) -- but living on separate nav
 * entries made that distinction invisible. Combined here as a section switcher instead:
 * one destination, the difference stated up front instead of implied by two menu items.
 */
export default function GovernancePage() {
  const [section, setSection] = useState<Section>("guide");
  const gov = useApiResource((s) => getGovernance(s), []);
  const { session } = useAuth();

  return (
    <>
      <PageHeader
        title={section === "guide" ? "Getting Started" : "Governance"}
        description={
          section === "guide"
            ? "What AEGIS is and how to use it — for the first time you sign in."
            : "The controls that make AEGIS more than a language model with a chat window: deterministic policy, evidence authority, and human accountability, read directly from what enforces them."
        }
        actions={
          <div className="flex items-center gap-2">
            <SectionSwitch section={section} onChange={setSection} />
            {section === "governance" && (
              <Button variant="secondary" onClick={gov.refresh} loading={gov.loading}>
                Refresh
              </Button>
            )}
          </div>
        }
      />

      <PageBody className="space-y-6">
        {section === "guide" ? (
          <GuideSection session={session} />
        ) : gov.error ? (
          <ErrorState message={gov.error.userMessage} action={<Button onClick={gov.refresh}>Try again</Button>} />
        ) : !gov.data ? (
          <Card>
            <CardBody>
              <SkeletonText lines={10} />
            </CardBody>
          </Card>
        ) : (
          <>
            {/* --- authentication, first and unambiguous ---------------- */}
            <Notice tone="info" title={`Authentication: ${gov.data.authentication.status}`}>
              {gov.data.authentication.detail}
              <br />
              <br />
              <strong>Planned:</strong> {gov.data.authentication.planned}
            </Notice>

            {/* --- prohibited actions ------------------------------------ */}
            <Card>
              <CardHeader
                title="Prohibited actions"
                description={`Policy contract ${gov.data.policy_contract_version} — ${gov.data.prohibited_actions.status}`}
              />
              <CardBody className="space-y-5">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
                    Three independent enforcement layers
                  </p>
                  <ol className="mt-2 space-y-2">
                    {gov.data.prohibited_actions.enforcement.map((line, i) => (
                      <li key={i} className="flex gap-2.5 text-[13px] leading-relaxed text-[var(--text-secondary)]">
                        <span className="mt-0.5 shrink-0 font-mono text-[11px] text-[var(--text-tertiary)]">
                          {i + 1}
                        </span>
                        {line}
                      </li>
                    ))}
                  </ol>
                </div>

                <div className="grid gap-4 lg:grid-cols-3">
                  {Object.entries(gov.data.prohibited_actions.by_workflow).map(([wf, contract]) => (
                    <div
                      key={wf}
                      className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] p-3.5"
                    >
                      <p className="text-[13px] font-semibold text-[var(--text-primary)]">
                        {WORKFLOW_LABELS[wf as keyof typeof WORKFLOW_LABELS] ?? humanize(wf)}
                      </p>
                      <p className="mt-2 text-[11px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                        Banned terms ({contract.banned_terms.length})
                      </p>
                      <ul className="mt-1 flex flex-wrap gap-1">
                        {contract.banned_terms.slice(0, 6).map((term) => (
                          <li
                            key={term}
                            className="rounded-[var(--radius-sm)] bg-[var(--status-blocked-bg)] px-1.5 py-0.5 text-[11px] text-[var(--status-blocked-fg)]"
                          >
                            “{term}”
                          </li>
                        ))}
                        {contract.banned_terms.length > 6 && (
                          <li className="text-[11px] text-[var(--text-tertiary)]">
                            +{contract.banned_terms.length - 6} more
                          </li>
                        )}
                      </ul>
                      <p className="mt-2 text-[11px] font-medium uppercase tracking-wider text-[var(--text-tertiary)]">
                        Banned fields
                      </p>
                      <p className="mt-1 font-mono text-[11px] text-[var(--text-secondary)]">
                        {contract.banned_field_names.join(", ")}
                      </p>
                    </div>
                  ))}
                </div>
              </CardBody>
            </Card>

            {/* --- approver roles ----------------------------------------- */}
            <Card>
              <CardHeader
                title="Approver roles and structure"
                description="Who is accountable for each workflow's terminal decision"
              />
              <CardBody className="grid gap-4 lg:grid-cols-3">
                {Object.entries(gov.data.approver_roles).map(([wf, role]) => (
                  <div
                    key={wf}
                    className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] p-3.5"
                  >
                    <p className="text-[13px] font-semibold text-[var(--text-primary)]">
                      {WORKFLOW_LABELS[wf as keyof typeof WORKFLOW_LABELS] ?? humanize(wf)}
                    </p>
                    <p className="mt-1.5 text-[12px] text-[var(--text-secondary)]">
                      {role.primary.join(", ")}
                    </p>
                    {role.escalation && (
                      <p className="mt-1 text-[11px] text-[var(--text-tertiary)]">
                        Escalates to: {role.escalation}
                      </p>
                    )}
                    {role.veto_role && (
                      <Badge tone="blocked" size="xs" className="mt-2">
                        Veto: {role.veto_role}
                      </Badge>
                    )}
                    {role.required_legs && (
                      <Badge tone="pending" size="xs" className="mt-2">
                        Dual approval — both legs required
                      </Badge>
                    )}
                    <p className="mt-2 text-[11px] leading-relaxed text-[var(--text-tertiary)]">
                      {role.structure}
                    </p>
                  </div>
                ))}
              </CardBody>
            </Card>

            {/* --- HITL rules --------------------------------------------- */}
            <Card>
              <CardHeader title="Human-in-the-loop rules" description={gov.data.hitl_rules.source} />
              <CardBody className="space-y-4">
                <div className="flex flex-wrap gap-3">
                  {Object.entries(gov.data.hitl_rules.escalation_ladder_hours).map(([tier, hours]) => (
                    <div
                      key={tier}
                      className="rounded-[var(--radius-md)] bg-[var(--surface-sunken)] px-3 py-2 text-center"
                    >
                      <p className="tnum text-lg font-semibold text-[var(--text-primary)]">{hours}h</p>
                      <p className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)]">
                        {humanize(tier)}
                      </p>
                    </div>
                  ))}
                </div>
                <ul className="space-y-1.5">
                  {gov.data.hitl_rules.invariants.map((rule, i) => (
                    <li key={i} className="flex gap-2 text-[13px] text-[var(--text-secondary)]">
                      <span aria-hidden="true" className="mt-0.5 shrink-0 text-[var(--status-ok-fg)]">
                        ✓
                      </span>
                      {rule}
                    </li>
                  ))}
                </ul>
                <Notice tone="warning" title="Escalation clock status">
                  {gov.data.hitl_rules.clock_status}
                </Notice>
              </CardBody>
            </Card>

            {/* --- evidence authority --------------------------------------- */}
            <Card>
              <CardHeader title="Evidence authority" description={gov.data.evidence_authority.source} />
              <CardBody className="space-y-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[13px] text-[var(--text-secondary)]">Citable statuses:</span>
                  {gov.data.evidence_authority.citable_statuses.map((s) => (
                    <Badge key={s} tone="ok" size="xs">
                      {s}
                    </Badge>
                  ))}
                  <span className="ml-3 text-[13px] text-[var(--text-secondary)]">
                    Broadening ceiling per run:
                  </span>
                  <span className="tnum font-medium">
                    {gov.data.evidence_authority.broadening_ceiling_per_run}
                  </span>
                </div>
                <p className="text-[13px] leading-relaxed text-[var(--text-secondary)]">
                  {gov.data.evidence_authority.enforcement}
                </p>
                <p className="text-[13px] leading-relaxed text-[var(--text-secondary)]">
                  {gov.data.evidence_authority.cache_rule}
                </p>
              </CardBody>
            </Card>

            {/* --- authentication detail --------------------------------- */}
            <Card>
              <CardHeader title="Roles referenced by the domain" />
              <CardBody>
                <ul className="flex flex-wrap gap-2">
                  {gov.data.authentication.roles_referenced_by_the_domain.map((role) => (
                    <li
                      key={role}
                      className="rounded-[var(--radius-full)] border border-[var(--border-default)] px-2.5 py-1 text-[12px] text-[var(--text-secondary)]"
                    >
                      {role}
                    </li>
                  ))}
                </ul>
              </CardBody>
            </Card>
          </>
        )}
      </PageBody>
    </>
  );
}

function SectionSwitch({ section, onChange }: { section: Section; onChange: (s: Section) => void }) {
  return (
    <div
      role="tablist"
      aria-label="Getting Started or Governance"
      className="flex rounded-[var(--radius-md)] border border-[var(--border-default)] p-0.5"
    >
      {(["guide", "governance"] as const).map((s) => (
        <button
          key={s}
          type="button"
          role="tab"
          aria-selected={section === s}
          onClick={() => onChange(s)}
          className={cn(
            "rounded-[calc(var(--radius-md)-2px)] px-3 py-1 text-[13px] font-medium transition-colors",
            section === s
              ? "bg-[var(--brand-subtle)] text-[var(--brand)]"
              : "text-[var(--text-secondary)] hover:bg-[var(--surface-sunken)]",
          )}
        >
          {s === "guide" ? "Getting Started" : "Governance"}
        </button>
      ))}
    </div>
  );
}

function GuideSection({ session }: { session: { display_name: string; role: string } | null }) {
  return (
    <div className="max-w-3xl space-y-6">
      <Card>
        <CardHeader title="What this is" />
        <CardBody className="space-y-3 text-[13px] leading-relaxed text-[var(--text-secondary)]">
          <p>
            AEGIS is decision support, not a decision-maker. For six regulated
            workflows — batch release, pharmacovigilance intake, supply planning,
            research review, clinical integrity, and regulatory completeness — it
            retrieves real evidence, drafts a finding, and pauses. Nothing it drafts
            becomes real until a named, accountable human — you, or whoever holds that
            approval role — reviews the cited evidence and decides.
          </p>
          <p>
            Every claim it makes must cite retrievable evidence. If it can&apos;t find
            enough to support a claim, it says so — it does not guess.
          </p>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Where things are" />
        <CardBody className="space-y-3">
          <GuideRow to="/" label="Overview" body="Your ten-second read: what's waiting for a decision, is anything unhealthy, and recent activity." />
          <GuideRow to="/workflows" label="Workflows" body="Start here to submit a new run — pick a workflow and a subject (a batch ID, a case ID, a product ID)." />
          <GuideRow to="/decisions" label="Decision Queue" body="Runs paused at a human checkpoint, waiting for someone with the right role to approve, reject, or veto." />
          <GuideRow to="/runs" label="Run History" body="Every run ever recorded, with its full audit trail — nothing is deleted or overwritten." />
          <GuideRow to="/evidence" label="Evidence" body="The evidence corpus a draft is allowed to cite, and what makes a piece of evidence authoritative." />
          <GuideRow to="/health" label="System Health" body="Live status of every dependency this system relies on (the database, the model, the cache)." />
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Submitting and deciding a run" />
        <CardBody className="space-y-3 text-[13px] leading-relaxed text-[var(--text-secondary)]">
          <ol className="list-decimal space-y-2 pl-5">
            <li>
              Open <Link href="/workflows" className="text-[var(--brand)] underline underline-offset-2">Workflows</Link>,
              choose a workflow, and submit a subject. Any signed-in role may submit any
              workflow — requesting a review doesn&apos;t require the authority to decide
              it, the same way a real requester commissions an analysis without being
              the one who signs off on it.
            </li>
            <li>
              The run pauses at its human-in-the-loop checkpoint and appears in the{" "}
              <Link href="/decisions" className="text-[var(--brand)] underline underline-offset-2">Decision Queue</Link>.
            </li>
            <li>
              Only a role authorized for that specific workflow (and leg, for the two
              requiring dual approval) can approve, reject, or veto it — enforced by the
              Orchestrator API on every request, not just hidden in the UI. Your own
              authority is listed below, in the Governance section.
            </li>
          </ol>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="If the model fails" />
        <CardBody className="space-y-3 text-[13px] leading-relaxed text-[var(--text-secondary)]">
          <p>
            If the language model is unreachable or errors out mid-run, AEGIS does not
            retry silently and does not guess at an answer. The run <strong>abstains</strong>{" "}
            with a clear, recorded reason (visible in Run History) instead of producing an
            unverified result. This is a deliberate design choice (ADR-007): in a
            regulated workflow, a safe stop is preferable to a blind retry that could
            record a decision no model actually reasoned through.
          </p>
        </CardBody>
      </Card>

      {session && (
        <Card>
          <CardHeader title="Signed in as you" />
          <CardBody className="flex flex-wrap items-center gap-2 text-[13px] text-[var(--text-secondary)]">
            <span>
              {session.display_name} — <Badge tone="neutral" size="xs">{session.role}</Badge>
            </span>
            <span>See the Governance section above for exactly what your role may decide.</span>
          </CardBody>
        </Card>
      )}
    </div>
  );
}

function GuideRow({ to, label, body }: { to: string; label: string; body: string }) {
  return (
    <Link
      href={to}
      className="block rounded-[var(--radius-md)] border border-[var(--border-subtle)] px-3.5 py-2.5 hover:bg-[var(--surface-sunken)]"
    >
      <p className="text-[13px] font-semibold text-[var(--text-primary)]">{label}</p>
      <p className="mt-0.5 text-[12px] leading-relaxed text-[var(--text-secondary)]">{body}</p>
    </Link>
  );
}
