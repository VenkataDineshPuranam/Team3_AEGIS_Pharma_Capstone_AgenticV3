"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { Textarea } from "@/components/ui/Form";
import { ErrorState, Notice } from "@/components/ui/States";
import { useAuth } from "@/components/layout/AuthContext";
import { HitlTimerBadge } from "@/components/decisions/HitlTimerBadge";
import { ApiError, decideRun, type DecisionAction, type QueueEntry, type SupplyLeg } from "@/lib/api";
import { WORKFLOW_BOUNDARY } from "@/lib/format";
import { emitQueueChanged } from "@/lib/queueEvents";

/** Mirrors services/api/schemas.py MIN_JUSTIFICATION_CHARS. Enforced by the API too. */
const MIN_JUSTIFICATION = 12;

interface PendingDecision {
  action: DecisionAction;
  leg?: SupplyLeg;
}

/**
 * The human action panel — the point of the entire product.
 *
 * Every action here follows the same two-step: choose, then justify and confirm. That is
 * not friction for its own sake. The justification is written into the append-only audit
 * record by the graph itself, so a decision recorded without one would be a decision no
 * one can later account for. The dialog is where it is collected because a person should
 * be looking at what they are about to assert when they type it.
 *
 * This panel enforces nothing. It collects and submits. Whether the veto stands, whether
 * one leg suffices, and what a timeout means are all decided by the backend graph, which
 * would reach the same conclusions if this UI did not exist.
 */
export function ApprovalPanel({
  entry,
  onDecided,
}: {
  entry: QueueEntry;
  onDecided: () => void;
}) {
  const { session } = useAuth();
  const role = session?.role ?? "";
  const identity = session?.display_name ?? "";
  const [pending, setPending] = useState<PendingDecision | null>(null);
  const [justification, setJustification] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [touched, setTouched] = useState(false);
  // Stage 21 gap-closure (INJ-071: automation bias -- a reviewer accepting an AI summary
  // despite an omitted critical exception). This is a distinct control from the
  // justification: a long justification can still be written without anyone having
  // actually looked at the exceptions section, whereas this checkbox cannot be checked
  // without the reviewer taking the action of reading them first.
  const [exceptionsAcknowledged, setExceptionsAcknowledged] = useState(false);

  const isDual = (entry.required_legs?.length ?? 0) > 1;
  const isPV = entry.workflow === "pv_intake";
  const boundary = WORKFLOW_BOUNDARY[entry.workflow];
  const uncitedCount = entry.draft_claims.filter((c) => c.cites.length === 0).length;
  const requiresExceptionsAck = uncitedCount > 0;

  const tooShort = justification.trim().length < MIN_JUSTIFICATION;
  const validationError =
    touched && tooShort
      ? `A justification of at least ${MIN_JUSTIFICATION} characters is required and will be permanently recorded.`
      : null;

  function open(action: DecisionAction, leg?: SupplyLeg) {
    setPending({ action, leg });
    setJustification("");
    setTouched(false);
    setError(null);
    setExceptionsAcknowledged(false);
  }

  function close() {
    if (submitting) return;
    setPending(null);
  }

  const exceptionsAckBlocking =
    requiresExceptionsAck && pending?.action === "approved" && !exceptionsAcknowledged;

  async function confirm() {
    if (!pending || tooShort || exceptionsAckBlocking) {
      setTouched(true);
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await decideRun(entry.run_id, {
        workflow: entry.workflow,
        action: pending.action,
        justification: justification.trim(),
        claimed_identity: identity.trim() || role,
        leg: pending.leg ?? null,
      });
      setPending(null);
      emitQueueChanged();
      onDecided();
    } catch (e) {
      // Deliberately no retry. The request may have been recorded; only the human can
      // decide whether to act again, so they are told exactly that.
      setError(e instanceof ApiError ? e : new ApiError(String(e), 0));
    } finally {
      setSubmitting(false);
    }
  }

  const copy = pending ? ACTION_COPY[pending.action] : null;

  return (
    <>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
            Approval status
          </p>
          <HitlTimerBadge timer={entry.hitl_timer} />
        </div>

        {/* Who is accountable, and for what. Phase 12's questions, answered in order. */}
        <div className="rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--surface-sunken)] px-3.5 py-3">
          <dl className="space-y-2 text-[13px]">
            <div className="flex flex-wrap gap-x-2">
              <dt className="text-[var(--text-tertiary)]">Governed approver:</dt>
              <dd className="font-medium text-[var(--text-primary)]">
                {entry.approver_roles.join(" and ") || "—"}
              </dd>
            </div>
            <div className="flex flex-wrap gap-x-2">
              <dt className="text-[var(--text-tertiary)]">You are signed in as:</dt>
              <dd className="font-medium text-[var(--text-primary)]">
                {identity} <span className="font-normal text-[var(--text-tertiary)]">({role})</span>
              </dd>
            </div>
            <div className="flex flex-wrap gap-x-2">
              <dt className="text-[var(--text-tertiary)]">You are reviewing:</dt>
              <dd className="text-[var(--text-primary)]">{boundary.produces}</dd>
            </div>
          </dl>
        </div>

        {isDual && (
          <DualApprovalProgress
            required={entry.required_legs ?? []}
            approved={entry.approved_legs}
            roles={entry.approver_roles}
          />
        )}

        {/* --- the controls -------------------------------------------- */}
        {isDual ? (
          <DualApprovalControls entry={entry} onOpen={open} busy={submitting} />
        ) : entry.viewer_can_approve_reject || entry.viewer_can_veto ? (
          <div className="flex flex-wrap gap-2">
            {entry.viewer_can_approve_reject && (
              <>
                <Button variant="primary" size="md" onClick={() => open("approved")}>
                  Approve
                </Button>
                <Button variant="danger" size="md" onClick={() => open("rejected")}>
                  Reject
                </Button>
              </>
            )}
            {isPV && entry.viewer_can_veto && (
              <Button variant="danger-strong" size="md" onClick={() => open("veto")}>
                Register veto
              </Button>
            )}
          </div>
        ) : (
          <Notice tone="info" title="You cannot decide this run">
            The governed approver for this run is {entry.approver_roles.join(" and ") || "a different role"} —
            your signed-in role ({role}) is not authorized to approve, reject, or veto it.
            You can still read everything above; deciding it requires signing in as an
            eligible role.
          </Notice>
        )}

        {isPV && (
          <p className="text-[11px] leading-relaxed text-[var(--text-tertiary)]">
            The advisory veto is the Patient Safety Representative&apos;s. Registering one
            forces the governed state to rejected immediately, and it cannot be overridden by
            any later approval — the audit store refuses such a write at the point of
            recording it. There is no override control here because there is no override.
          </p>
        )}

        {/* No control anywhere on this page can release a batch, determine causality, or
            move inventory. Those capabilities do not exist in the backend, so there is
            nothing here that could invoke them. */}
      </div>

      {/* --- confirmation with justification ---------------------------- */}
      <Dialog
        open={pending !== null}
        onClose={close}
        busy={submitting}
        size="lg"
        title={copy?.title ?? ""}
        description={copy?.description}
        footer={
          <>
            <Button variant="ghost" size="md" onClick={close} disabled={submitting}>
              Cancel
            </Button>
            <Button
              variant={pending?.action === "approved" ? "primary" : "danger-strong"}
              size="md"
              onClick={confirm}
              loading={submitting}
              loadingLabel="Recording…"
              disabled={exceptionsAckBlocking}
            >
              {copy?.confirm}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <dl className="grid grid-cols-2 gap-3 rounded-[var(--radius-md)] bg-[var(--surface-sunken)] px-3.5 py-3 text-[12px]">
            <div>
              <dt className="text-[var(--text-tertiary)]">Subject</dt>
              <dd className="mt-0.5 font-mono font-medium text-[var(--text-primary)]">
                {entry.subject_id}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--text-tertiary)]">Run</dt>
              <dd className="mt-0.5 font-mono text-[var(--text-primary)]">{entry.run_id}</dd>
            </div>
            {pending?.leg && (
              <div>
                <dt className="text-[var(--text-tertiary)]">Approval leg</dt>
                <dd className="mt-0.5 font-medium text-[var(--text-primary)]">
                  {pending.leg === "planning" ? "Planning (Supply Chain VP)" : "Quality (EU QP)"}
                </dd>
              </div>
            )}
            <div>
              <dt className="text-[var(--text-tertiary)]">Recorded as</dt>
              <dd className="mt-0.5 text-[var(--text-primary)]">{identity.trim() || role}</dd>
            </div>
          </dl>

          {copy?.warning && (
            <Notice tone={pending?.action === "veto" ? "blocked" : "warning"} title={copy.warning.title}>
              {copy.warning.body}
            </Notice>
          )}

          {requiresExceptionsAck && pending?.action === "approved" && (
            <label className="flex items-start gap-2.5 rounded-[var(--radius-md)] border border-[var(--status-pending-border)] bg-[var(--status-pending-bg)] px-3.5 py-3 text-[13px]">
              <input
                type="checkbox"
                checked={exceptionsAcknowledged}
                onChange={(e) => setExceptionsAcknowledged(e.target.checked)}
                className="mt-0.5 size-3.5 shrink-0 accent-[var(--brand)]"
              />
              <span className="text-[var(--text-primary)]">
                This run has <strong>{uncitedCount}</strong> claim{uncitedCount === 1 ? "" : "s"} with
                no supporting citation. I have read the Exceptions section on the Decision
                Support tab and am approving with that gap accounted for, not because the
                summary read as complete.
              </span>
            </label>
          )}

          <Textarea
            label="Justification"
            required
            rows={5}
            value={justification}
            onChange={(e) => setJustification(e.target.value)}
            onBlur={() => setTouched(true)}
            error={validationError}
            autoFocus
            hint="Written verbatim into the append-only audit record, attributed to the governed approver role. It cannot be edited or removed afterwards."
            placeholder={copy?.placeholder}
          />

          <p className="text-[11px] text-[var(--text-tertiary)]">
            <span className="tnum">{justification.trim().length}</span> characters — minimum{" "}
            <span className="tnum">{MIN_JUSTIFICATION}</span>.
          </p>

          {error && (
            <ErrorState
              title="The decision was not confirmed as recorded"
              message={error.userMessage}
              hint={
                error.status === 0
                  ? "This request is never retried automatically, because a repeat could record a second decision you did not make. Reload the queue to check whether it was recorded before acting again."
                  : "No retry was attempted. Check the run's audit timeline before acting again."
              }
            />
          )}
        </div>
      </Dialog>
    </>
  );
}

/**
 * Dual-approval state.
 *
 * Phase 14's rule made visual: one approval never reads as complete approval. The final
 * governed state is stated as its own line, in the outstanding-leg's colour, so a
 * half-approved run cannot be mistaken for a done one at any glance distance.
 */
function DualApprovalProgress({
  required,
  approved,
  roles,
}: {
  required: string[];
  approved: string[];
  roles: string[];
}) {
  const legRole: Record<string, string> = {
    planning: roles[0] ?? "Supply Chain VP",
    quality: roles[1] ?? "EU Qualified Person",
  };
  const outstanding = required.filter((leg) => !approved.includes(leg));
  const complete = outstanding.length === 0;

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--border-default)] bg-[var(--surface-raised)] p-3.5">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
        Dual approval — both legs required
      </p>
      <ul className="mt-2.5 space-y-2">
        {required.map((leg) => {
          const done = approved.includes(leg);
          return (
            <li key={leg} className="flex items-center justify-between gap-3">
              <span className="min-w-0">
                <span className="block text-[13px] font-medium text-[var(--text-primary)]">
                  {legRole[leg]}
                </span>
                <span className="block text-[11px] text-[var(--text-tertiary)]">{leg} leg</span>
              </span>
              <Badge tone={done ? "ok" : "pending"} size="sm">
                {done ? "Approved" : "Pending"}
              </Badge>
            </li>
          );
        })}
      </ul>

      <div
        className={`mt-3 flex flex-wrap items-center gap-2 border-t pt-3 ${
          complete ? "border-[var(--status-ok-border)]" : "border-[var(--status-pending-border)]"
        }`}
      >
        <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
          Final governed state
        </span>
        <Badge tone={complete ? "ok" : "pending"}>
          {complete
            ? "Both approvals recorded"
            : `Awaiting ${outstanding.map((l) => legRole[l]).join(" and ")}`}
        </Badge>
      </div>

      {!complete && approved.length > 0 && (
        <p className="mt-2 text-[11px] leading-relaxed text-[var(--status-pending-fg)]">
          Partial approval is not approval. If the window expires with one leg outstanding,
          no action is taken — the run abstains exactly as it would with no approval at all.
        </p>
      )}
    </div>
  );
}

function DualApprovalControls({
  entry,
  onOpen,
  busy,
}: {
  entry: QueueEntry;
  onOpen: (action: DecisionAction, leg?: SupplyLeg) => void;
  busy: boolean;
}) {
  const legs: { key: SupplyLeg; label: string }[] = [
    { key: "planning", label: "Planning leg" },
    { key: "quality", label: "Quality leg" },
  ];

  return (
    <div className="space-y-2">
      {legs.map((leg) => {
        const done = entry.approved_legs.includes(leg.key);
        const canDecideThisLeg = entry.viewer_decidable_legs.includes(leg.key);
        return (
          <div
            key={leg.key}
            className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-md)] border border-[var(--border-subtle)] px-3 py-2.5"
          >
            <span className="text-[13px] font-medium text-[var(--text-primary)]">{leg.label}</span>
            {done ? (
              <Badge tone="ok" size="sm">
                Recorded
              </Badge>
            ) : canDecideThisLeg ? (
              <span className="flex gap-2">
                <Button
                  variant="primary"
                  disabled={busy}
                  onClick={() => onOpen("approved", leg.key)}
                >
                  Approve {leg.key}
                </Button>
                <Button variant="danger" disabled={busy} onClick={() => onOpen("rejected", leg.key)}>
                  Reject
                </Button>
              </span>
            ) : (
              <span className="text-[12px] text-[var(--text-tertiary)]">Not your leg to decide</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

const ACTION_COPY: Record<
  DecisionAction,
  {
    title: string;
    description: string;
    confirm: string;
    placeholder: string;
    warning?: { title: string; body: string };
  }
> = {
  approved: {
    title: "Confirm approval",
    description:
      "You are recording that you, as the accountable approver, have reviewed this decision-support package and accept it.",
    confirm: "Confirm approval",
    placeholder:
      "State what you reviewed and why you accept it — for example the findings and evidence you relied on, and any residual uncertainty you accept.",
    warning: {
      title: "This is recorded permanently",
      body: "Your approval and justification are written to an append-only audit store. They cannot be edited or withdrawn.",
    },
  },
  rejected: {
    title: "Confirm rejection",
    description: "You are recording that this decision-support package is not accepted.",
    confirm: "Confirm rejection",
    placeholder:
      "State why you are rejecting — for example a gap, conflict, or insufficiency in the findings or the evidence supporting them.",
    warning: {
      title: "This is recorded permanently",
      body: "Your rejection and its reason are written to an append-only audit store and cannot be edited or withdrawn.",
    },
  },
  veto: {
    title: "Register a patient safety veto",
    description:
      "The Patient Safety Representative's advisory veto. This is the strongest control available to a human in this workflow.",
    confirm: "Register veto",
    placeholder:
      "State the patient safety concern that grounds this veto. This text is the permanent record of why the veto was registered.",
    warning: {
      title: "A veto cannot be overridden",
      body: "The governed state becomes rejected immediately. No later approval — by anyone, at any tier — can supersede it: the audit store rejects such a write at the point of recording. There is no override, and no control anywhere in this application offers one.",
    },
  },
  timed_out: {
    title: "Record timeout",
    description: "The approval window expired.",
    confirm: "Record timeout",
    placeholder: "",
  },
};
