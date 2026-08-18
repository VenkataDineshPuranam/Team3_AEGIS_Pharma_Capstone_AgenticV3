"use client";

import Link from "next/link";
import { PageBody, PageHeader } from "@/components/layout/AppShell";
import { useAuth } from "@/components/layout/AuthContext";
import { Badge } from "@/components/ui/Badge";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";

/**
 * Getting Started -- a first-time-user walkthrough of the product itself: what each
 * screen is for, how to submit and decide a run, and what happens when something fails.
 *
 * Deliberately NOT a duplicate of the Governance page. Governance is an enforcement
 * reference (what's actually enforced and why, sourced live from the code that enforces
 * it -- see governance_view.py's module docstring). This page is orientation: someone's
 * first five minutes, written for a person who has never seen AEGIS before, not for
 * someone auditing a control.
 */
export default function GuidePage() {
  const { session } = useAuth();

  return (
    <>
      <PageHeader
        title="Getting Started"
        description="What AEGIS is, how to use it, and what to expect — for the first time you sign in."
      />
      <PageBody className="max-w-3xl space-y-6">
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
            <GuideRow
              to="/"
              label="Overview"
              body="Your ten-second read: what's waiting for a decision, is anything unhealthy, and recent activity."
            />
            <GuideRow
              to="/workflows"
              label="Workflows"
              body="Start here to submit a new run — pick a workflow and a subject (a batch ID, a case ID, a product ID)."
            />
            <GuideRow
              to="/decisions"
              label="Decision Queue"
              body="Runs paused at a human checkpoint, waiting for someone with the right role to approve, reject, or veto."
            />
            <GuideRow
              to="/runs"
              label="Run History"
              body="Every run ever recorded, with its full audit trail — nothing is deleted or overwritten."
            />
            <GuideRow
              to="/evidence"
              label="Evidence"
              body="The evidence corpus a draft is allowed to cite, and what makes a piece of evidence authoritative."
            />
            <GuideRow
              to="/governance"
              label="Governance"
              body="The enforcement reference: exact policy contracts, approver roles, and HITL rules, read live from the code that enforces them."
            />
            <GuideRow
              to="/health"
              label="System Health"
              body="Live status of every dependency this system relies on (the database, the model, the cache)."
            />
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
                authority is listed on the login screen and in{" "}
                <Link href="/governance" className="text-[var(--brand)] underline underline-offset-2">Governance</Link>.
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
              <span>
                See <Link href="/governance" className="text-[var(--brand)] underline underline-offset-2">Governance</Link>{" "}
                for exactly what your role may decide.
              </span>
            </CardBody>
          </Card>
        )}
      </PageBody>
    </>
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
