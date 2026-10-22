/** @vitest-environment happy-dom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PlanInboxView, type PlanInboxViewProps } from "@/components/plan-inbox/PlanInboxView";
import type { InboxPlanCard } from "@/lib/planInboxScreen";

const NOW = new Date("2026-10-05T20:00:00Z");

const R4: InboxPlanCard = {
  plan_hash: "b8e2c4417a0f9d36",
  schema_fp: "sfp_c9",
  goal: "Restart the invoice sequence",
  status: "pending",
  max_risk: "R4",
  environment: "production",
  expires_at: "2026-10-06T14:00:00+00:00",
  requester_id: "usr_tunde",
  approvals: [{ approver_id: "usr_kemi", user_id: "usr_kemi", decision: "approve" }],
  r3_blockers: ["distinct_approvers", "backup"],
  risk: { max: "R4", per_op: ["R4"], policy: { allow: true, approvers: 2, needs_backup: true } },
  sections: [{ title: "goal and assumptions", body: "Restart the invoice sequence" }],
  changes: [{ type: "sequence.update", description: "Set sequence prefix", params: { number_next: 1 } }],
};

const EXPIRED: InboxPlanCard = { ...R4, plan_hash: "e3017c55d2a98b14", max_risk: "R2", approvals: [], r3_blockers: [], risk: { policy: { approvers: 1 } }, expires_at: "2026-10-05T17:00:00Z" };

function props(overrides: Partial<PlanInboxViewProps> = {}): PlanInboxViewProps {
  return {
    connectionId: "conn-1",
    onConnectionChange: vi.fn(),
    onOpen: vi.fn(),
    onRefresh: vi.fn(),
    phase: "ready",
    plans: [R4, EXPIRED],
    loadedConnectionId: "conn-1",
    selectedHash: R4.plan_hash,
    onSelect: vi.fn(),
    viewerId: "usr_amaka",
    decision: { busy: null, message: null, failure: null },
    onDecide: vi.fn(),
    now: NOW,
    timeZone: "Africa/Lagos",
    ...overrides,
  };
}

afterEach(cleanup);

describe("PlanInboxView", () => {
  it("shows two approver slots on production heavy R4, one filled, and the distinct-person rule", () => {
    render(<PlanInboxView {...props()} />);
    const slots = screen.getAllByTestId("plan-card-slot");
    expect(slots).toHaveLength(2);
    expect(slots[0]).toHaveTextContent("usr_kemi");
    expect(slots[1]).toHaveTextContent("Open");
    expect(screen.getByTestId("plan-card-distinct-note")).toHaveTextContent("different person");
    expect(screen.getByTestId("plan-card-blockers")).toHaveTextContent("No backup id is recorded");
    expect(screen.getByTestId("plan-card-approve")).toBeEnabled();
    expect(screen.getByTestId("plan-inbox-count")).toHaveTextContent("1 waiting of 2");
  });

  it("blocks the first approver from filling the second slot", () => {
    render(<PlanInboxView {...props({ viewerId: "usr_kemi" })} />);
    expect(screen.getByTestId("plan-card-approve")).toBeDisabled();
    expect(screen.getByTestId("plan-card-gate-title")).toHaveTextContent("You already approved this fingerprint");
    expect(screen.getAllByTestId("plan-card-slot")[0]).toHaveTextContent("usr_kemi (you)");
  });

  it("hides decision buttons on an expired plan and explains it", () => {
    render(<PlanInboxView {...props({ selectedHash: EXPIRED.plan_hash })} />);
    expect(screen.getByTestId("plan-card-status")).toHaveTextContent("Expired");
    expect(screen.queryByTestId("plan-card-approve")).not.toBeInTheDocument();
    expect(screen.getByTestId("plan-card-status-guide-why")).toHaveTextContent("Expired 3 hours ago");
    expect(screen.getByTestId("plan-inbox-step-2")).toHaveAttribute("data-state", "blocked");
  });

  it("keeps Open inbox as the primary only when no plan list is shown", () => {
    const { container, rerender } = render(<PlanInboxView {...props({ phase: "idle", plans: [] })} />);
    expect(screen.getByRole("button", { name: "Open inbox" }).className).toMatch(/bg-accent/);
    expect(screen.getByTestId("plan-inbox-idle-title")).toHaveTextContent("Pick a connection");
    rerender(<PlanInboxView {...props()} />);
    expect(container.querySelectorAll("button.bg-accent")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Open inbox" }).className).not.toMatch(/bg-accent/);
  });

  it("shows amber caution for an open R4 and walks the rail with arrow keys", () => {
    const onSelect = vi.fn();
    render(<PlanInboxView {...props({ onSelect })} />);
    expect(screen.getByTestId("plan-card-caution-title")).toHaveTextContent("Heavy R4 on production");
    const rows = screen.getAllByTestId("plan-inbox-row");
    rows[0].focus();
    fireEvent.keyDown(rows[0], { key: "ArrowDown" });
    expect(onSelect).toHaveBeenCalledWith(EXPIRED.plan_hash);
    expect(document.activeElement).toBe(rows[1]);
  });

  it("uses the stage rail to separate approval from the executor apply", () => {
    render(<PlanInboxView {...props()} />);
    expect(screen.getByTestId("plan-inbox-step-1")).toHaveTextContent("Engine plan");
    expect(screen.getByTestId("plan-inbox-step-2")).toHaveAttribute("aria-current", "step");
    expect(screen.getByTestId("plan-inbox-step-3")).toHaveTextContent("Executor apply");
  });
});
