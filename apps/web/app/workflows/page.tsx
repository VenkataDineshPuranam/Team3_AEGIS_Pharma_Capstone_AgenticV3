"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { PageBody, PageHeader } from "@/components/layout/AppShell";
import { useAuth } from "@/components/layout/AuthContext";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Select } from "@/components/ui/Form";
import { ErrorState, Notice } from "@/components/ui/States";
import { WorkflowChip } from "@/components/domain/Chips";
import { ApiError, submitRun, type Workflow } from "@/lib/api";
import { WORKFLOW_BOUNDARY, WORKFLOW_LABELS, WORKFLOW_SUBJECT_LABEL } from "@/lib/format";
import { emitQueueChanged } from "@/lib/queueEvents";

// tests/fixtures/synthetic/* -- the only subject ids the backend can actually resolve in
// this build. Listing exactly these rather than a free-text field keeps this page from
// promising a batch/case/product the API cannot serve.
const SUBJECT_OPTIONS: Record<Workflow, string[]> = {
  batch_review: [
    "B-001", "B-002", "B-003", "B-004", "B-005", "B-006", "B-007", "B-008", "B-009",
    "B-010", "B-011", "B-012", "B-013", "B-014", "B-015", "B-016",
  ],
  pv_intake: ["PV-001", "PV-002", "PV-003", "PV-004", "PV-005"],
  supply_planning: ["P-100", "P-200", "P-300"],
  research_review: ["R-001", "R-002", "R-003", "R-004", "R-005", "R-006", "R-007"],
  clinical_integrity: [
    "CT-001", "CT-002", "CT-003", "CT-004", "CT-005", "CT-006", "CT-007", "CT-008", "CT-009",
  ],
  regulatory_completeness: ["REG-001", "REG-002", "REG-003", "REG-004", "REG-005", "REG-006", "REG-007"],
};

const DEFAULT_ROLE: Record<Workflow, string> = {
  batch_review: "EU Qualified Person",
  pv_intake: "Global Head of Pharmacovigilance",
  supply_planning: "Supply Chain VP",
  research_review: "Head of Preclinical Research",
  clinical_integrity: "Clinical Trial Medical Monitor",
  regulatory_completeness: "Head of Regulatory Affairs",
};

const WORKFLOWS: Workflow[] = [
  "batch_review", "pv_intake", "supply_planning",
  "research_review", "clinical_integrity", "regulatory_completeness",
];

/**
 * Workflows — what each workflow may and may not conclude, plus the ability to start a run.
 *
 * Phase 11's requirement that workflows not be forced into one UI starts here: the three
 * boundary statements are the product's clearest explanation of what AEGIS is for, and
 * they are shown before the form that starts a run, not after.
 */
export default function WorkflowsPage() {
  return (
    <>
      <PageHeader
        title="Workflows"
        description="AEGIS supports six independent governed workflows. Each produces decision support only — never a terminal safety, release, or execution decision."
      />
      <PageBody className="space-y-6">
        {WORKFLOWS.map((wf) => (
          <WorkflowSection key={wf} workflow={wf} />
        ))}
      </PageBody>
    </>
  );
}

function WorkflowSection({ workflow }: { workflow: Workflow }) {
  const boundary = WORKFLOW_BOUNDARY[workflow];
  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2.5">
            <WorkflowChip workflow={workflow} />
            {WORKFLOW_LABELS[workflow]}
          </span>
        }
        level={2}
      />
      <CardBody className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-2">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
              Produces
            </p>
            <p className="mt-1.5 text-[13px] leading-relaxed text-[var(--text-secondary)]">
              {boundary.produces}
            </p>
          </div>
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
              Never does
            </p>
            <ul className="mt-1.5 space-y-1">
              {boundary.neverDoes.map((item) => (
                <li key={item} className="flex items-start gap-2 text-[13px] text-[var(--text-secondary)]">
                  <span aria-hidden="true" className="mt-0.5 shrink-0 text-[var(--status-blocked-fg)]">
                    ⊘
                  </span>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <StartRunForm workflow={workflow} />
      </CardBody>
    </Card>
  );
}

function StartRunForm({ workflow }: { workflow: Workflow }) {
  const router = useRouter();
  const { session } = useAuth();
  const identity = session?.display_name ?? "";
  const [subjectId, setSubjectId] = useState(SUBJECT_OPTIONS[workflow][0]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<{ runId: string; pending: boolean } | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const r = await submitRun({
        workflow,
        subject_id: subjectId,
        requester_role: session?.role || DEFAULT_ROLE[workflow],
      });
      setResult({ runId: r.run_id, pending: r.status === "pending_approval" });
      if (r.status === "pending_approval") emitQueueChanged();
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError(String(err), 0));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--surface-sunken)] p-4">
      <form onSubmit={onSubmit} className="flex flex-wrap items-end gap-3">
        <div className="w-40">
          <Select
            label={WORKFLOW_SUBJECT_LABEL[workflow]}
            value={subjectId}
            onChange={(e) => setSubjectId(e.target.value)}
          >
            {SUBJECT_OPTIONS[workflow].map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </Select>
        </div>
        <Button type="submit" variant="primary" loading={busy} loadingLabel="Running…">
          Start run
        </Button>
        <p className="text-[11px] text-[var(--text-tertiary)]">
          Requested as {identity || "you"} ({session?.role || DEFAULT_ROLE[workflow]}). Runs
          against the real governed graph — this synchronously executes retrieval, synthesis,
          guard and Critic passes.
        </p>
      </form>

      {error && (
        <ErrorState
          className="mt-3"
          message={error.userMessage}
          hint="No retry was attempted for this submission."
        />
      )}

      {result && (
        <Notice
          tone={result.pending ? "info" : "ok"}
          className="mt-3"
          title={result.pending ? "Run is awaiting a decision" : "Run finalized"}
        >
          <span className="font-mono">{result.runId}</span>
          {" — "}
          <button
            type="button"
            onClick={() =>
              router.push(
                result.pending
                  ? `/decisions/${encodeURIComponent(result.runId)}`
                  : `/runs/${encodeURIComponent(result.runId)}`,
              )
            }
            className="underline underline-offset-2"
          >
            {result.pending ? "Open in the Decision Queue" : "View the recorded outcome"}
          </button>
        </Notice>
      )}
    </div>
  );
}
