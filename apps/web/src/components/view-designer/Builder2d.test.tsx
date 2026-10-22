import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const m = vi.hoisted(() => ({
  industries: vi.fn(), comments: vi.fn(), hideUnused: vi.fn(), a11yFix: vi.fn(), commentAdd: vi.fn(),
  tiles: vi.fn(), tilePreview: vi.fn(), tileSave: vi.fn(), approvers: vi.fn(), setApprovers: vi.fn(), pauses: vi.fn(), approvals: vi.fn(), approvalDiff: vi.fn(),
  listConnections: vi.fn(), promoteCompare: vi.fn(),
}));
vi.mock("@/lib/api", () => ({
  api: Object.fromEntries(Object.keys(m).map((k) => [k, (...a: unknown[]) => (m as Record<string, (...x: unknown[]) => unknown>)[k](...a)])),
}));
const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

import { Insights2d, Publishing2d, Tiles2d, type P2d } from "./Builder2d";

const base = (over: Partial<P2d> = {}): P2d => ({
  connectionId: "c1", model: "sale.order", viewType: "form", viewId: null, onSample: vi.fn(), onChanged: vi.fn(), errorText: String,
  fields: { date_order: { string: "Order Date", type: "datetime" }, amount_total: { string: "Total", type: "monetary" } }, ...over,
});

beforeEach(() => {
  Object.values(m).forEach((f) => f.mockReset());
  m.listConnections.mockResolvedValue([{ id: "c1", name: "Here" }, { id: "c2", name: "Live v20" }]);
  m.industries.mockResolvedValue({ industries: ["retail"], note: "" });
  m.comments.mockResolvedValue({ comments: [], resolved: 0 });
  m.tiles.mockResolvedValue({ tiles: [] });
  m.approvers.mockResolvedValue({ approvers: {} });
  m.pauses.mockResolvedValue({ pauses: [], paused_now: false, note: null });
  m.approvals.mockResolvedValue({ approvals: [{ id: "a1", payload: { status: "pending" } }] });
});
afterEach(() => cleanup());

describe("View Designer stage 2d", () => {
  it("hide unused fields adds draft changes; comments need a selected item", async () => {
    m.hideUnused.mockResolvedValue({ ops: [{ op: "set_attr", node: "field:note", attr: "invisible", value: "1" }], labels: ["Note"], total: 40, note: "1 field is empty" });
    const onAddOps = vi.fn();
    render(<Insights2d {...base({ onAddOps })} />);
    fireEvent.click(screen.getByText("Hide fields nobody fills in"));
    await waitFor(() => expect(onAddOps).toHaveBeenCalledWith([{ op: "set_attr", node: "field:note", attr: "invisible", value: "1" }], "Hide 1 unused field"));
    expect((screen.getByText("Add").closest("button") as HTMLButtonElement).disabled).toBe(true);
  });

  it("tiles preview shows the comparison", async () => {
    m.tilePreview.mockResolvedValue({ label: "Number of sale.order", value: 12, previous: 10, change: "Up 20% on last month." });
    render(<Tiles2d {...base()} />);
    fireEvent.click(screen.getByText("Preview"));
    expect(await screen.findByText(/Up 20% on last month/)).toBeTruthy();
    expect(m.tilePreview.mock.calls[0][1]).toMatchObject({ measure: "__count", date_field: "date_order", period: "month" });
  });

  it("publishing shows what a pending request changes and saves approvers", async () => {
    m.approvalDiff.mockResolvedValue({ changes: [{ kind: "removed", node: "field:email", text: "Removed: Email" }], note: "" });
    m.setApprovers.mockResolvedValue({ approvers: { "sale.order": ["boss@x.com"] } });
    render(<Publishing2d {...base()} />);
    fireEvent.click(await screen.findByText("Show what changes"));
    expect(await screen.findByText("Removed: Email")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Approvers"), { target: { value: "boss@x.com" } });
    fireEvent.click(screen.getAllByText("Save")[0]);
    await waitFor(() => expect(m.setApprovers).toHaveBeenCalledWith("c1", { "sale.order": ["boss@x.com"] }));
  });

  it("compares a screen side by side with another database", async () => {
    m.promoteCompare.mockResolvedValue({
      source: { major: 18, items: [{ node: "field:a", tag: "field", label: "Alpha", hidden: false }] },
      target_now: { major: 20, items: [] },
      target_after: { items: [{ node: "field:a", tag: "field", label: "Alpha", hidden: false }] },
      changes: [{ kind: "added", node: "field:a", text: "Added: Alpha" }], still_different: [], problems: [], note: "Nothing changes until someone approves the move in the other database.",
    });
    render(<Publishing2d {...base()} />);
    fireEvent.change(await screen.findByLabelText("Target database"), { target: { value: "c2" } });
    expect(screen.queryByRole("option", { name: "Here" })).toBeNull();
    fireEvent.click(screen.getByText("Compare side by side"));
    expect(await screen.findByText("There now (Odoo 20)")).toBeTruthy();
    expect(screen.getByText(/1 change there/)).toBeTruthy();
    expect(m.promoteCompare.mock.calls[0][2]).toBe("c2");
  });
});
