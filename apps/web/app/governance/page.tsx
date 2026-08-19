"use client";

import { useState } from "react";
import Image from "next/image";
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
        actions={<SectionSwitch section={section} onChange={setSection} />}
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
    <>
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

    <VisualTour />
    </>
  );
}

/**
 * A screenshot of each page with numbered red arrows pointing at what matters on it --
 * the same walkthrough a colleague would give standing over your shoulder, for the
 * (common) case where nobody is available to do that. Screenshots are static (taken from
 * a real Super Admin / EU Qualified Person session, not mocked up) and live in
 * apps/web/public/guide/ -- they age as the UI changes, same tradeoff every screenshot
 * guide makes, and are worth regenerating whenever a page's layout changes materially.
 */
function VisualTour() {
  return (
    <div className="mt-2 max-w-5xl space-y-10">
      <div>
        <h2 className="text-lg font-semibold tracking-tight text-[var(--text-primary)]">
          A visual tour
        </h2>
        <p className="mt-1 text-[13px] leading-relaxed text-[var(--text-secondary)]">
          Every numbered red arrow below points at something real on that page. The list
          under each screenshot explains what it is and why it matters — read it once and
          the rest of the app stops needing a legend.
        </p>
      </div>

      {TOUR_PAGES.map((page) => (
        <Card key={page.name} as="section">
          <CardHeader title={page.title} description={page.description} />
          <CardBody className="space-y-4">
            <Image
              src={`/guide/${page.name}.png`}
              alt={`Annotated screenshot of the ${page.title} page`}
              width={page.width}
              height={page.height}
              sizes="(min-width: 1024px) 960px, 100vw"
              className="h-auto w-full rounded-[var(--radius-md)] border border-[var(--border-subtle)]"
            />
            <ol className="grid gap-2.5 sm:grid-cols-2">
              {page.legend.map((item) => (
                <li key={item.number} className="flex gap-2.5 text-[13px] leading-relaxed">
                  <span
                    aria-hidden="true"
                    className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-[var(--status-blocked-fg)] text-[11px] font-semibold text-white"
                  >
                    {item.number}
                  </span>
                  <span className="text-[var(--text-secondary)]">
                    <strong className="font-semibold text-[var(--text-primary)]">{item.title}</strong>
                    {" — "}
                    {item.body}
                  </span>
                </li>
              ))}
            </ol>
          </CardBody>
        </Card>
      ))}
    </div>
  );
}

const TOUR_PAGES: {
  name: string;
  title: string;
  description: string;
  width: number;
  height: number;
  legend: { number: number; title: string; body: string }[];
}[] = [
  {
    name: "overview",
    title: "Overview",
    description: "The screen every role lands on first — signed in as Super Admin here",
    width: 1440,
    height: 1250,
    legend: [
      { number: 1, title: "Sidebar navigation", body: "Every destination your role can see. Items outside your role — Compliance, Evaluation & Security — are hidden here, not just blocked after a click." },
      { number: 2, title: "Notification bell", body: "HITL escalation alerts. A red count means a pending run has crossed a severity tier and needs attention sooner." },
      { number: 3, title: "Awaiting decision", body: "How many runs are paused for a human right now, across every workflow. Click through to the Decision Queue." },
      { number: 4, title: "Decision queue (preview)", body: "The oldest pending runs, condensed from the full Decision Queue page. \"Open queue\" goes to the complete list." },
      { number: 5, title: "Recent activity", body: "The most recently finalized runs across every workflow, with their outcome (completed, abstained, refused, blocked)." },
      { number: 6, title: "System health", body: "Live status of every dependency the system needs — policy engine, audit store, Neo4j, Redis, the LLM provider." },
    ],
  },
  {
    name: "decision-queue",
    title: "Decision Queue",
    description: "Every run currently paused at a human-in-the-loop checkpoint",
    width: 1440,
    height: 850,
    legend: [
      { number: 1, title: "Page title", body: "Runs that have already passed evidence retrieval, the prohibited-action guard, and Critic verification — and now cannot complete until an accountable human decides." },
      { number: 2, title: "Search", body: "Filter by run id, subject id, summary text, or approver role." },
      { number: 3, title: "\"Awaiting your role\"", body: "Show only the runs your own signed-in role is actually eligible to decide — useful once the queue has runs for several different approvers in it." },
      { number: 4, title: "Refresh", body: "The one page in the app that kept a manual refresh button — everywhere else refreshes itself, but this is the page you watch, so an explicit \"check right now\" earns its place." },
    ],
  },
  {
    name: "decision-detail",
    title: "Deciding a run",
    description: "Opening a pending run — the actual Approve / Reject flow",
    width: 1440,
    height: 900,
    legend: [
      { number: 1, title: "Human decision required", body: "States plainly who the governed approver is, who you are signed in as, and what you are being asked to certify — before you see a single button." },
      { number: 2, title: "Approve", body: "Records your decision, with a required justification, to the append-only audit store. Only visible if your signed-in role is the actual governed approver for this run — computed server-side, never assumed from the UI." },
      { number: 3, title: "Reject", body: "Same, recording a rejection. For a Batch Review rejection specifically, this also mints a citable precedent (Shadow QP, ADR-010) that a later run with a similar gap can retrieve as evidence — never as an auto-approval." },
      { number: 4, title: "Structured findings tab", body: "The same findings in machine-readable form, each one traced to the exact evidence it cites — the same facts the summary prose is written from, in a form you can check line by line." },
    ],
  },
  {
    name: "run-history",
    title: "Run History",
    description: "Every run ever recorded — nothing is deleted or overwritten",
    width: 1440,
    height: 850,
    legend: [
      { number: 1, title: "Page title", body: "The append-only audit store's own read view. A record is written once, when a run finalizes, and can never be edited." },
      { number: 2, title: "Search", body: "Filter by run id or subject id across the full history, server-side (not just the page currently loaded)." },
      { number: 3, title: "Export audit report", body: "Downloads the complete run and decision history as a CSV — visible only to Super Admin, Auditor, and Unblinding authority, the three roles with no decide authority anywhere in the system." },
    ],
  },
  {
    name: "evidence",
    title: "Evidence",
    description: "The knowledge-graph corpus a run is allowed to cite from",
    width: 1440,
    height: 950,
    legend: [
      { number: 1, title: "Page title", body: "Every document a governed run could retrieve — and, deliberately, several it cannot, shown here so you can see why." },
      { number: 2, title: "How to read these states", body: "The four authority states, made visually distinct on purpose: a non-citable item can never be mistaken for an authoritative one, in color or in greyscale." },
      { number: 3, title: "Documents", body: "Total corpus size, split into what a run can retrieve (citable) and what is excluded server-side before a run ever sees it." },
    ],
  },
  {
    name: "workflows",
    title: "Workflows",
    description: "The six governed workflows this system supports, and where a run starts",
    width: 1440,
    height: 900,
    legend: [
      { number: 1, title: "Page title", body: "AEGIS supports six independent governed workflows. Each produces decision support only — never a terminal safety, release, or execution decision." },
      { number: 2, title: "Workflow card", body: "What this workflow produces, what it structurally never does (not a policy promise — the output schema has no field that could represent it), and a \"Start run\" control to submit a real subject against the live governed graph." },
    ],
  },
  {
    name: "system-health",
    title: "System Health",
    description: "Measured dependency status — the result of a real probe, not configuration",
    width: 1440,
    height: 950,
    legend: [
      { number: 1, title: "Page title", body: "Every entry here is the result of an actual probe run at the time shown, not an inference from an environment variable being set." },
      { number: 2, title: "Orchestrator API", body: "The API itself: which of the six workflows it's serving, and how many runs are currently awaiting a decision." },
      { number: 3, title: "Dependencies", body: "Four distinct states (ok / degraded / unavailable / not configured), so a missing credential and a genuine outage are never shown the same way." },
      { number: 4, title: "Audit store", body: "Where the append-only database actually lives on disk, and a live count of every record type it holds." },
    ],
  },
  {
    name: "chaos-drill",
    title: "Chaos Drill",
    description: "Proving the fail-closed claims, not just asserting them — Super Admin / CISO-DPO only",
    width: 1440,
    height: 1000,
    legend: [
      { number: 1, title: "Page title", body: "Named fail-closed injectors for degraded-mode claims. Restricted, on both the nav and the API, to Super Admin and CISO / DPO." },
      { number: 2, title: "Lab drills", body: "Five named injectors — LLM provider unreachable, HITL timer expiry, and Neo4j / Redis / policy-engine unavailable — each with a specific, checkable claim about what the system should do." },
      { number: 3, title: "Run", body: "Forces one failure on a fresh, isolated graph and records what the system actually did. Shared Neo4j, Redis, and API processes are never taken down." },
    ],
  },
  {
    name: "coverage",
    title: "Evaluation & Security",
    description: "What has actually been verified, and what has not — Super Admin only",
    width: 1440,
    height: 1000,
    legend: [
      { number: 1, title: "Page title", body: "System-wide verification posture. Every status on this page cites a real file — nothing here is an estimate." },
      { number: 2, title: "Coverage by dimension", body: "The 13 risk dimensions from the original tabletop exercise this system's scope was built against, each scenario mapped to a real control, test, or document — or, honestly, to a registered gap." },
    ],
  },
  {
    name: "compliance",
    title: "Compliance",
    description: "EU AI Act and ISO 42001 evidence, read live from the governance docs — Super Admin only",
    width: 1440,
    height: 1000,
    legend: [
      { number: 1, title: "Page title", body: "Parsed live from the actual governance documents that make each claim — not a second, hand-maintained copy that could drift from what's true." },
      { number: 2, title: "Evidence discipline banner", body: "An honest summary, not a compliance claim: every clause is addressed by a real artifact or a tracked, owned gap. The page states directly, right below this banner, that a risk tier is a reasoned classification, not a legal determination." },
      { number: 3, title: "EU AI Act — boundary-pack questions", body: "The actual regulatory questions this system's classification answers, each with a citation into the code or docs that makes it true." },
    ],
  },
  {
    name: "governance",
    title: "Governance",
    description: "The live enforcement reference — read from the code and policy that actually enforce each rule",
    width: 1440,
    height: 1000,
    legend: [
      { number: 1, title: "Page title", body: "Unlike a policy document, this page is generated from the same files the running system enforces against — if the code changes, this page changes with it." },
      { number: 2, title: "Prohibited actions", body: "The three independent enforcement layers (schema absence, tool-capability absence, runtime guard) that make a disposition structurally unrepresentable, shown per workflow with its actual banned terms and fields." },
      { number: 3, title: "Getting Started / Governance toggle", body: "Switch back to this walkthrough at any time — the two used to be separate nav entries people kept mistaking for duplicates, so they're one page now." },
    ],
  },
];

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
