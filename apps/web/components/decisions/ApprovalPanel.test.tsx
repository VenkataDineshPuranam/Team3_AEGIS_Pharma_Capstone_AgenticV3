import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "@/components/layout/AuthContext";
import { setSession } from "@/lib/auth/session";
import type { QueueEntry } from "@/lib/api";
import { ApprovalPanel } from "./ApprovalPanel";

setSession({
  token: "test-token",
  user_id: "test_qp",
  display_name: "Test QP",
  role: "EU Qualified Person",
  expires_at: new Date(Date.now() + 3600_000).toISOString(),
});

const decideRunMock = vi.fn();

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, decideRun: (...args: unknown[]) => decideRunMock(...args) };
});

function batchEntry(overrides: Partial<QueueEntry> = {}): QueueEntry {
  return {
    run_id: "R-1",
    workflow: "batch_review",
    subject_id: "B-001",
    requester_role: "EU Qualified Person",
    approver_roles: ["EU Qualified Person"],
    required_legs: [],
    approved_legs: [],
    draft_summary: "Batch B-001 findings",
    draft_claims: [],
    created_at: new Date().toISOString(),
    evidence: [],
    domain_payload: null,
    evidence_accounting: null,
    hitl_timer: { tier: "T0", label: "On time", severity: 1, hours_elapsed: 0.1, hours_to_next_tier: 7.9 },
    // Every existing test in this file signs in as "EU Qualified Person" and exercises
    // the decide controls directly -- the eligibility gate itself (Stage 25) has its own
    // dedicated tests below and at the API layer (test_api_read_endpoints.py), so these
    // fixtures default to "eligible" to keep every pre-existing test's assumptions true.
    viewer_can_approve_reject: true,
    viewer_can_veto: true,
    viewer_decidable_legs: ["planning", "quality"],
    ...overrides,
  };
}

function pvEntry(): QueueEntry {
  return batchEntry({ workflow: "pv_intake", subject_id: "PV-001", approver_roles: ["Global Head of Pharmacovigilance"] });
}

function supplyEntry(approved: string[] = []): QueueEntry {
  return batchEntry({
    workflow: "supply_planning",
    subject_id: "P-100",
    approver_roles: ["Supply Chain VP", "EU Qualified Person"],
    required_legs: ["planning", "quality"],
    approved_legs: approved,
  });
}

function renderPanel(entry: QueueEntry, onDecided = vi.fn()) {
  return render(
    <AuthProvider>
      <ApprovalPanel entry={entry} onDecided={onDecided} />
    </AuthProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("ApprovalPanel -- decide eligibility (Stage 25)", () => {
  it("hides Approve/Reject and explains why when the viewer cannot decide this run", () => {
    renderPanel(
      batchEntry({
        approver_roles: ["EU Qualified Person"],
        viewer_can_approve_reject: false,
        viewer_can_veto: false,
      }),
    );

    expect(screen.queryByRole("button", { name: "Approve" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
    expect(screen.getByText(/you cannot decide this run/i)).toBeInTheDocument();
  });

  it("shows Approve/Reject when the viewer can decide this run", () => {
    renderPanel(batchEntry({ viewer_can_approve_reject: true }));

    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });

  it("gates each dual-approval leg independently", () => {
    // Only the quality leg is decidable by this viewer -- the planning leg should show
    // an explanatory message instead of a clickable Approve/Reject pair.
    renderPanel(batchEntry({
      workflow: "supply_planning",
      subject_id: "P-100",
      approver_roles: ["Supply Chain VP", "EU Qualified Person"],
      required_legs: ["planning", "quality"],
      approved_legs: [],
      viewer_decidable_legs: ["quality"],
    }));

    expect(screen.getByText("Not your leg to decide")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve quality" })).toBeInTheDocument();
  });
});

describe("ApprovalPanel -- justification (G-10)", () => {
  it("does not call the API when Confirm is pressed with no justification typed", async () => {
    const user = userEvent.setup();
    renderPanel(batchEntry());

    await user.click(screen.getByRole("button", { name: "Approve" }));
    await user.click(screen.getByRole("button", { name: "Confirm approval" }));

    expect(decideRunMock).not.toHaveBeenCalled();
    expect(await screen.findByText(/at least 12 characters/i)).toBeInTheDocument();
  });

  it("submits the justification verbatim once it meets the minimum length", async () => {
    const user = userEvent.setup();
    decideRunMock.mockResolvedValue({ status: "completed" });
    const onDecided = vi.fn();
    renderPanel(batchEntry(), onDecided);

    await user.click(screen.getByRole("button", { name: "Approve" }));
    await user.type(
      screen.getByLabelText(/justification/i),
      "Genealogy and lab packet reconcile against K-006.",
    );
    await user.click(screen.getByRole("button", { name: "Confirm approval" }));

    await waitFor(() => expect(decideRunMock).toHaveBeenCalledTimes(1));
    expect(decideRunMock).toHaveBeenCalledWith(
      "R-1",
      expect.objectContaining({
        action: "approved",
        justification: "Genealogy and lab packet reconcile against K-006.",
      }),
    );
    await waitFor(() => expect(onDecided).toHaveBeenCalled());
  });

  it("does not clear the typed justification into React state after the API rejects it", async () => {
    const user = userEvent.setup();
    const { ApiError } = await import("@/lib/api");
    decideRunMock.mockRejectedValue(new ApiError("boom", 500));
    renderPanel(batchEntry());

    await user.click(screen.getByRole("button", { name: "Approve" }));
    await user.type(screen.getByLabelText(/justification/i), "A justification long enough to submit.");
    await user.click(screen.getByRole("button", { name: "Confirm approval" }));

    // The dialog stays open on failure -- nothing here silently discards the human's
    // typed words or pretends the action succeeded.
    expect(await screen.findByText(/was not confirmed as recorded/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/justification/i)).toHaveValue(
      "A justification long enough to submit.",
    );
  });

  it("never retries automatically after a failed submission", async () => {
    const user = userEvent.setup();
    const { ApiError } = await import("@/lib/api");
    decideRunMock.mockRejectedValue(new ApiError("boom", 500));
    renderPanel(batchEntry());

    await user.click(screen.getByRole("button", { name: "Approve" }));
    await user.type(screen.getByLabelText(/justification/i), "A justification long enough to submit.");
    await user.click(screen.getByRole("button", { name: "Confirm approval" }));

    await screen.findByText(/was not confirmed as recorded/i);
    // Give any hidden retry timer a chance to fire.
    await new Promise((r) => setTimeout(r, 50));
    expect(decideRunMock).toHaveBeenCalledTimes(1);
  });
});

describe("ApprovalPanel -- automation-bias attestation (INJ-071)", () => {
  it("does not require the attestation checkbox when every claim is cited", async () => {
    const user = userEvent.setup();
    decideRunMock.mockResolvedValue({ status: "completed" });
    renderPanel(batchEntry({ draft_claims: [{ text: "Fully cited.", cites: ["K-006"] }] }));

    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("blocks Confirm until the attestation is checked when a claim is uncited", async () => {
    const user = userEvent.setup();
    renderPanel(batchEntry({ draft_claims: [{ text: "No citation for this one.", cites: [] }] }));

    await user.click(screen.getByRole("button", { name: "Approve" }));
    await user.type(screen.getByLabelText(/justification/i), "Reviewed the exceptions and accept the gap.");

    const confirmButton = screen.getByRole("button", { name: "Confirm approval" });
    expect(confirmButton).toBeDisabled();

    await user.click(screen.getByRole("checkbox"));
    expect(confirmButton).toBeEnabled();
  });

  it("does not require the attestation for rejection, only for approval", async () => {
    const user = userEvent.setup();
    renderPanel(batchEntry({ draft_claims: [{ text: "No citation.", cites: [] }] }));

    await user.click(screen.getByRole("button", { name: "Reject" }));
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});

describe("ApprovalPanel -- PV veto", () => {
  it("offers a veto control for pv_intake and not for batch_review", async () => {
    renderPanel(pvEntry());
    expect(screen.getByRole("button", { name: /register veto/i })).toBeInTheDocument();
  });

  it("offers no veto control for batch_review", () => {
    renderPanel(batchEntry());
    expect(screen.queryByRole("button", { name: /veto/i })).not.toBeInTheDocument();
  });

  it("states there is no override anywhere near the veto control", () => {
    renderPanel(pvEntry());
    expect(screen.getByText(/no override control here because there is no override/i)).toBeInTheDocument();
  });

  it("labels the veto confirmation as non-overridable", async () => {
    const user = userEvent.setup();
    renderPanel(pvEntry());
    await user.click(screen.getByRole("button", { name: /register veto/i }));
    const matches = await screen.findAllByText(/cannot be overridden/i);
    expect(matches.length).toBeGreaterThan(0);
  });
});

describe("ApprovalPanel -- supply_planning dual approval", () => {
  it("never shows a single approval as complete approval", () => {
    renderPanel(supplyEntry(["planning"]));
    // The planning leg legitimately shows "Approved" -- the thing that must never appear
    // with only one leg in is the FINAL GOVERNED STATE reading as complete.
    expect(screen.getByText(/awaiting eu qualified person/i)).toBeInTheDocument();
    expect(screen.queryByText(/both approvals recorded/i)).not.toBeInTheDocument();
    expect(screen.getByText(/partial approval is not approval/i)).toBeInTheDocument();
  });

  it("shows both approvals recorded only once both legs are present", () => {
    renderPanel(supplyEntry(["planning", "quality"]));
    expect(screen.getByText(/both approvals recorded/i)).toBeInTheDocument();
  });

  it("submits the correct leg when approving the quality leg", async () => {
    const user = userEvent.setup();
    decideRunMock.mockResolvedValue({ status: "pending_approval" });
    renderPanel(supplyEntry(["planning"]));

    await user.click(screen.getByRole("button", { name: /approve quality/i }));
    await user.type(
      screen.getByLabelText(/justification/i),
      "Cold-chain constraints verified against K-009.",
    );
    await user.click(screen.getByRole("button", { name: "Confirm approval" }));

    await waitFor(() =>
      expect(decideRunMock).toHaveBeenCalledWith(
        "R-1",
        expect.objectContaining({ action: "approved", leg: "quality" }),
      ),
    );
  });

  it("does not offer approve/reject controls for a leg already approved", () => {
    renderPanel(supplyEntry(["planning"]));
    const planningRow = screen.getByText("Planning leg").closest("div")!;
    expect(within(planningRow).getByText("Recorded")).toBeInTheDocument();
    expect(within(planningRow).queryByRole("button")).toBeNull();
  });
});
