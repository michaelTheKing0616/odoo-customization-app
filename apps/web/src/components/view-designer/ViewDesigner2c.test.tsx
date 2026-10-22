import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { EngineNode } from "@/lib/api/view-engine";

const m = vi.hoisted(() => ({
  fieldDeps: vi.fn(),
  requiredImpact: vi.fn(),
  saveBlockers: vi.fn(),
  heatmap: vi.fn(),
  sampleData: vi.fn(),
  a11y: vi.fn(),
  explainScreen: vi.fn(),
  approvalPolicy: vi.fn(),
  approvals: vi.fn(),
  listConnections: vi.fn(),
  schedules: vi.fn(),
  watches: vi.fn(),
  approvalRequest: vi.fn(),
  approvalDecide: vi.fn(),
  scheduleCreate: vi.fn(),
  watchUndo: vi.fn(),
  coedit: vi.fn(),
  watchStart: vi.fn(),
  industries: vi.fn(),
  comments: vi.fn(),
  approvers: vi.fn(),
  pauses: vi.fn(),
  tiles: vi.fn(),
}));
vi.mock("@/lib/api", () => ({
  api: Object.fromEntries(Object.keys(m).map((k) => [k, (...a: unknown[]) => (m as Record<string, (...x: unknown[]) => unknown>)[k](...a)])),
}));
const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

import { Builder2cSheet, type Props2c } from "./Builder2cSheet";
import { EngineCanvas } from "./EngineCanvas";
import { FieldDepsPanel, RequiredImpact, TourCard } from "./Insights2c";
import { indexTree } from "@/lib/viewEngineOps";
import { renderHook } from "@testing-library/react";
import { useDesigner2c } from "./useDesigner2c";

const errorText = (e: unknown) => String(e);
const n = (id: string, tag: string, children: EngineNode[] = [], extra: Partial<EngineNode> = {}): EngineNode => ({
  id, tag, kind: tag === "field" ? "field" : "container", name: id.split(":")[1] ?? null, label: id.split(":")[1] ?? tag, attrs: {},
  anchor: `//${tag}[@name='${id.split(":")[1]}']`, locked_reason: null, children, ...extra,
});
const tree = n("root", "form", [n("sheet:s", "sheet", [n("group:a", "group", [n("field:name", "field"), n("field:email", "field")])])], { kind: "root" });

beforeEach(() => {
  Object.values(m).forEach((f) => f.mockReset());
  m.approvalPolicy.mockResolvedValue({ required: false, you: null, identity_verified: false, note: "Sign-in is off here, so Ingenium can't tell who asks and who approves." });
  m.approvals.mockResolvedValue({ approvals: [] });
  m.listConnections.mockResolvedValue([]);
  m.schedules.mockResolvedValue({ scheduled: [] });
  m.watches.mockResolvedValue({ watches: [] });
  m.industries.mockResolvedValue({ industries: [], note: "" });
  m.comments.mockResolvedValue({ comments: [], resolved: 0 });
  m.approvers.mockResolvedValue({ approvers: {} });
  m.pauses.mockResolvedValue({ pauses: [], paused_now: false, note: null });
  m.tiles.mockResolvedValue({ tiles: [] });
  toast.mockClear();
  toast.success.mockClear();
  toast.error.mockClear();
});
afterEach(() => cleanup());

const props = (over: Partial<Props2c> = {}): Props2c => ({
  open: true, onOpenChange: vi.fn(), tab: "insights", onTab: vi.fn(), connectionId: "c1", model: "res.partner", viewType: "form", viewId: null,
  ops: [], summary: [], layerHash: null, roles: [], fields: {}, heatOn: false, onHeat: vi.fn(), sampleOn: false, onSample: vi.fn(),
  simulate: "", onSimulate: vi.fn(), onTour: vi.fn(), onJump: vi.fn(), onOpenScreen: vi.fn(), onClearOps: vi.fn(), onChanged: vi.fn(), errorText, ...over,
});

describe("View Designer stage 2c", () => {
  it("dependency map: says plainly whether hiding is safe and lists where the field is used", async () => {
    m.fieldDeps.mockResolvedValue({
      field: "email", label: "Email", level: "caution", total: 2,
      verdict: "Email is used in 2 places. Hiding only changes this screen: the field keeps its value and everything below keeps working.",
      groups: [{ kind: "automation", title: "Automations", risk: "high", count: 1, items: [{ name: "Welcome mail", detail: "An automation watches or checks it." }] },
               { kind: "screen_rule", title: "This screen", risk: "high", count: 1, items: [{ name: "Phone", detail: "Its show/hide rule reads this field.", node: "field:phone" }] }],
    });
    const onJump = vi.fn();
    render(<FieldDepsPanel connectionId="c1" model="res.partner" viewType="form" viewId={null} field="email" onJump={onJump} errorText={errorText} />);
    fireEvent.click(screen.getByText("Check before hiding or removing"));
    expect(await screen.findByText(/keeps its value/)).toBeTruthy();
    expect(screen.getByText("Welcome mail")).toBeTruthy();
    fireEvent.click(screen.getByText("Show"));
    expect(onJump).toHaveBeenCalledWith("field:phone");
  });

  it("required impact: counts affected records for 'required when' rules only", async () => {
    m.requiredImpact.mockResolvedValue({ countable: true, matching: 10, missing: 3, text: "3 of 10 records where VIP is ticked have no Email yet." });
    const cond = { match: "all" as const, rules: [{ field: "is_vip", op: "is_true", value: null }] };
    const { rerender } = render(<RequiredImpact connectionId="c1" model="res.partner" field="email" condition={cond} errorText={errorText} />);
    expect(await screen.findByTestId("vd-required-impact")).toHaveProperty("textContent", "3 of 10 records where VIP is ticked have no Email yet.");
    rerender(<RequiredImpact connectionId="c1" model="res.partner" field="email" condition={cond} inverted errorText={errorText} />);
    expect(screen.getByText(/Counts are shown for/)).toBeTruthy();
  });

  it("insights: heatmap and labelled sample data are switched on through callbacks", async () => {
    m.heatmap.mockResolvedValue({ heat: { "field:name": { level: 4, label: "Filled on 100% of 5" } }, note: "Counts only." });
    m.sampleData.mockResolvedValue({ records: [{ id: -1, display_name: "Sample record 1", __sample: true, name: "Sample name 1" }], label: "Sample", note: "" });
    const p = props();
    render(<Builder2cSheet {...p} />);
    fireEvent.click(screen.getByText("Show heatmap"));
    await waitFor(() => expect(p.onHeat).toHaveBeenCalledWith({ "field:name": { level: 4, label: "Filled on 100% of 5" } }));
    fireEvent.click(screen.getByText("Use sample data"));
    await waitFor(() => expect(p.onSample).toHaveBeenCalled());
    expect((p.onSample as ReturnType<typeof vi.fn>).mock.calls[0][0].__sample).toBe(true);
  });

  it("insights: what blocks saving lists fields per stage", async () => {
    m.saveBlockers.mockResolvedValue({
      stage_field: "state", stage_label: "Status", summary: "Checked 2 stages. 1 of them need fields filled in before saving.",
      stages: [{ value: "done", label: "Done", always: [], at_stage: [{ field: "partner_id", label: "Customer", node: "field:partner_id", why: "Required on this screen at this stage.", missing_now: 4 }], depends: [] }],
    });
    render(<Builder2cSheet {...props()} />);
    fireEvent.click(screen.getByText("Check each stage"));
    expect(await screen.findByText(/Done: 1 must be filled/)).toBeTruthy();
    expect(screen.getByText(/4 records here are missing it now/)).toBeTruthy();
  });

  it("publishing: asks for approval with the draft and clears it; shows the sign-in note", async () => {
    m.approvalRequest.mockResolvedValue({ ok: true, item_id: "a1" });
    const p = props({ tab: "publishing", ops: [{ op: "hide", node: "field:email" }], summary: ["Hide Email"] });
    render(<Builder2cSheet {...p} />);
    expect(await screen.findByText(/can't tell who asks/)).toBeTruthy();
    fireEvent.click(screen.getByText("Ask for approval (1 change)"));
    await waitFor(() => expect(m.approvalRequest).toHaveBeenCalled());
    expect(m.approvalRequest.mock.calls[0][1]).toMatchObject({ ops: [{ op: "hide", node: "field:email" }], summary: ["Hide Email"] });
    await waitFor(() => expect(p.onClearOps).toHaveBeenCalled());
  });

  it("publishing: pending approvals can be approved; scheduling is off while approval is required", async () => {
    m.approvalPolicy.mockResolvedValue({ required: true, you: "b@x.com", identity_verified: true, note: null });
    m.approvals.mockResolvedValue({ approvals: [{ id: "a1", kind: "approval", key: "k", name: "Hide Email", created_at: null,
      payload: { status: "pending", requested_by: "a@x.com", identity_verified: true, summary: [], note: "" } }] });
    m.approvalDecide.mockResolvedValue({ ok: true, status: "approved" });
    const p = props({ tab: "publishing", ops: [{ op: "hide", node: "field:email" }] });
    render(<Builder2cSheet {...p} />);
    fireEvent.click(await screen.findByText("Approve and publish"));
    await waitFor(() => expect(m.approvalDecide).toHaveBeenCalledWith("c1", "a1", true, "", null));
    expect((screen.getByText("Schedule my changes").closest("button") as HTMLButtonElement).disabled).toBe(true);
  });

  it("tour card walks through the steps", () => {
    const onAt = vi.fn();
    const steps = [{ node: "root", title: "Overview", text: "This is the Contact screen." }, { node: "field:name", title: "Name", text: "Must be filled in." }];
    render(<TourCard steps={steps} at={0} onAt={onAt} onEnd={vi.fn()} />);
    expect(screen.getByText("This is the Contact screen.")).toBeTruthy();
    fireEvent.click(screen.getByText("Next"));
    expect(onAt).toHaveBeenCalledWith(1);
  });

  it("canvas shows heat, other editors and the tour focus", () => {
    render(
      <EngineCanvas tree={tree} index={indexTree(tree)} record={null} selectedId={null} onSelect={vi.fn()} onMove={vi.fn()} onInsertField={vi.fn()}
        heat={{ "field:name": { level: 3, label: "Filled on 80% of 10" } }} cursors={{ "field:email": ["ann@x.com"] }} tourFocus="field:name" />,
    );
    expect(screen.getByTestId("vd-heat").textContent).toBe("Filled on 80% of 10");
    expect(screen.getByTestId("vd-cursor").textContent).toBe("ann@x.com");
    expect(document.querySelector('[data-node-id="field:name"]')?.getAttribute("data-tour")).toBe("true");
    expect(document.querySelector('[data-node-id="field:email"]')?.getAttribute("data-others")).toBe("ann@x.com");
  });

  it("co-editing: shares new draft changes and applies other people's", async () => {
    vi.useFakeTimers();
    try {
      m.coedit.mockResolvedValueOnce({ seq: 1, ops: [], others: [{ editor_id: "e2", name: "ann@x.com", selected: "field:email" }], refused: [] });
      m.coedit.mockResolvedValueOnce({ seq: 3, ops: [{ seq: 3, editor: "e2", name: "ann@x.com", op: { op: "hide", node: "field:email" } }], others: [], refused: [] });
      const addOps = vi.fn();
      const s = { model: "res.partner", viewType: "form" as const, viewId: null, ops: [{ op: "hide" as const, node: "field:name" }], addOps, selectedId: "field:name", tree: {}, lastPublish: null };
      const { result } = renderHook(() => useDesigner2c(s, "c1"));
      await act(async () => { await vi.advanceTimersByTimeAsync(1600); });
      expect(m.coedit.mock.calls[0][1]).toMatchObject({ ops: [{ op: "hide", node: "field:name" }], selected: "field:name", since: 0 });
      expect(result.current.cursors).toEqual({ "field:email": ["ann@x.com"] });
      await act(async () => { await vi.advanceTimersByTimeAsync(1600); });
      expect(m.coedit.mock.calls[1][1]).toMatchObject({ ops: [], since: 1 });
      expect(addOps).toHaveBeenCalledWith([{ op: "hide", node: "field:email" }], "ann@x.com changed 1 item");
    } finally {
      vi.useRealTimers();
    }
  });
});
