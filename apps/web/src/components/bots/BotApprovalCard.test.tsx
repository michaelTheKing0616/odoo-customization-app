/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BotApprovalCard } from "./BotApprovalCard";
import type { BotApproval } from "@/lib/api/bot-approvals";

afterEach(() => cleanup());

const item = (
  over: Partial<BotApproval> = {},
  card: Partial<BotApproval["card"]> = {},
) =>
  ({
    id: "a1",
    connection_id: "c1",
    task_id: "m:res.partner.category:change",
    risk_class: "R3",
    n_records: 3,
    tier: 2,
    status: "pending",
    requested_by: "bot-1",
    decided_by: null,
    created_at: null,
    decided_at: null,
    ...over,
    card: {
      summary: "Rename tags",
      model: "res.partner.category",
      changes: [{ field: "name", to: "VIP" }],
      records: 3,
      risk: "R3",
      tier: 2,
      tier_label: "Needs your approval",
      reasons: ["This kind of change is rated level 2."],
      refusal: null,
      undo: {
        available: true,
        how: "One-click undo puts back the earlier values.",
      },
      rehearsal: { passed: true },
      limits: ["Text translated into other languages is not restored by undo."],
      ...card,
    },
  }) as BotApproval;

const JARGON = /\b(lane|grain|IR|RPC|hash|R\d)\b/;

describe("BotApprovalCard", () => {
  it("shows tier, count, reasons, undo and plain copy", () => {
    render(
      <BotApprovalCard
        item={item()}
        onApprove={() => {}}
        onReject={() => {}}
      />,
    );
    expect(screen.getByTestId("bot-approval-tier").textContent).toBe("Level 2");
    expect(screen.getByTestId("bot-approval-count").textContent).toContain(
      "exactly 3 records",
    );
    expect(screen.getByTestId("bot-approval-undo").textContent).toMatch(
      /undo/i,
    );
    const text = screen.getByTestId("bot-approval-card").textContent ?? "";
    expect(text).not.toMatch(JARGON);
    expect(text).not.toMatch(/\u2014/);
  });

  it("approve and reject call back with the plan id", () => {
    const onApprove = vi.fn();
    const onReject = vi.fn();
    render(
      <BotApprovalCard
        item={item()}
        onApprove={onApprove}
        onReject={onReject}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Approve 3 changes/ }));
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    expect(onApprove).toHaveBeenCalledWith("a1");
    expect(onReject).toHaveBeenCalledWith("a1");
  });

  it("locks buttons while a decision is in flight", () => {
    render(
      <BotApprovalCard
        item={item()}
        locked
        onApprove={() => {}}
        onReject={() => {}}
      />,
    );
    for (const b of screen.getAllByRole("button"))
      expect((b as HTMLButtonElement).disabled).toBe(true);
  });

  it("refused plan: honest refusal, no tier, no buttons", () => {
    const refusal =
      "It hasn't passed a practice run on a copy of your database yet.";
    render(
      <BotApprovalCard
        item={item(
          { status: "refused", tier: null },
          { tier: null, refusal, reasons: [] },
        )}
        onApprove={() => {}}
        onReject={() => {}}
      />,
    );
    expect(screen.getByTestId("bot-approval-refusal").textContent).toContain(
      refusal,
    );
    expect(screen.getByTestId("bot-approval-refusal").textContent).toContain(
      "Nothing in",
    );
    expect(screen.queryByTestId("bot-approval-tier")).toBeNull();
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it.each(["approved", "rejected", "auto"] as const)(
    "%s plan has no decision buttons",
    (status) => {
      render(
        <BotApprovalCard
          item={item({ status })}
          onApprove={() => {}}
          onReject={() => {}}
        />,
      );
      expect(screen.queryAllByRole("button")).toHaveLength(0);
    },
  );

  it("shows a decision error", () => {
    render(
      <BotApprovalCard item={item()} error="This plan is already approved." />,
    );
    expect(screen.getByTestId("bot-approval-error").textContent).toContain(
      "already approved",
    );
  });
});
