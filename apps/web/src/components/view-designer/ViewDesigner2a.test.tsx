import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { EngineNode } from "@/lib/api/view-engine";

const n = (id: string, tag: string, children: EngineNode[] = [], extra: Partial<EngineNode> = {}): EngineNode => ({
  id,
  tag,
  kind: tag === "field" ? "field" : "container",
  name: id.split(":")[1] ?? null,
  label: id.split(":")[1] ?? tag,
  attrs: {},
  anchor: `//${tag}[@name='${id.split(":")[1]}']`,
  locked_reason: null,
  children,
  ...extra,
});
const tree = n("root", "form", [
  n("sheet:main", "sheet", [
    n("group:a", "group", [
      n("field:phone", "field", [], { label: "Phone" }),
      n("field:mobile", "field", [], { label: "Mobile" }),
      n("field:email", "field", [], { label: "Email", attrs: { invisible: "not is_company" }, rules: { invisible: "Hidden when Is a company is not ticked" } }),
    ]),
  ]),
], { kind: "root" });

const m = vi.hoisted(() => ({
  compile: vi.fn(),
  fieldImpact: vi.fn(),
  previewAs: vi.fn(),
  command: vi.fn(),
  commentsAdd: vi.fn(),
  commentsList: vi.fn(),
  historyList: vi.fn(),
  historyCompare: vi.fn(),
  historyTree: vi.fn(),
  conditionWords: vi.fn(),
  modelAccess: vi.fn(),
  modelAccessPreview: vi.fn(),
  modelAccessApply: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    widgets: vi.fn(async () => ({ major: 19, widgets: [] })),
    defaultGet: vi.fn(async () => ({ value: null, set: false })),
    presence: vi.fn(async () => ({ others: [], ttl: 60 })),
    guardCheck: vi.fn(async () => ({ has_layer: false, ok: true, summary: "", steps: [] })),
    engineLoad: vi.fn(async () => ({
      major: 18, model: "crm.lead", view_type: "form", base_view_id: 1, combined_arch: "<form/>", arch_hash: "x", tree,
      fields: { phone: { string: "Phone", type: "char" }, mobile: { string: "Mobile", type: "char" }, email: { string: "Email", type: "char" }, stage_id: { string: "Stage", type: "many2one" } },
      layer: null,
    })),
    engineRecords: vi.fn(async () => ({ records: [{ id: 1, display_name: "A" }], total: 1, fields: [], picks: { longest: null, emptiest: null } })),
    engineCompile: (...a: unknown[]) => m.compile(...a),
    enginePublish: vi.fn(),
    engineRevert: vi.fn(),
    roles: vi.fn(async () => ({
      roles: [
        { xmlid: "sales_team.group_sale_manager", id: 2, name: "Sales / Administrator", people: 1 },
        { xmlid: "sales_team.group_sale_salesman", id: 1, name: "Sales / User", people: 3 },
      ],
      admin_role: "base.group_system",
      based_on: "Based on group rules.",
    })),
    people: vi.fn(async () => ({ people: [] })),
    previewAs: (...a: unknown[]) => m.previewAs(...a),
    fieldImpact: (...a: unknown[]) => m.fieldImpact(...a),
    command: (...a: unknown[]) => m.command(...a),
    commentsList: (...a: unknown[]) => m.commentsList(...a),
    commentsAdd: (...a: unknown[]) => m.commentsAdd(...a),
    commentsResolve: vi.fn(),
    commentsDelete: vi.fn(),
    historyList: (...a: unknown[]) => m.historyList(...a),
    historyCompare: (...a: unknown[]) => m.historyCompare(...a),
    historyTree: (...a: unknown[]) => m.historyTree(...a),
    historyName: vi.fn(),
    historyRestore: vi.fn(),
    conditionWords: (...a: unknown[]) => m.conditionWords(...a),
    conditionValues: vi.fn(async () => ({ type: "char", ops: [] })),
    conditionCheck: vi.fn(),
    modelAccess: (...a: unknown[]) => m.modelAccess(...a),
    modelAccessPreview: (...a: unknown[]) => m.modelAccessPreview(...a),
    modelAccessApply: (...a: unknown[]) => m.modelAccessApply(...a),
    modelAccessUndo: vi.fn(async () => ({ ok: true })),
    versions: vi.fn(async () => ({ current: 18, versions: [] })),
  },
}));
const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), message: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

import { ViewDesignerShell } from "./ViewDesignerShell";

const compiled = (expected: EngineNode = tree) => ({ arch: "<data/>", steps: [{ op: "x", xpath: [] }], dropped: [], warnings: [], issues: [], blocking: false, expected_tree: expected });

beforeEach(() => {
  window.history.replaceState(null, "", "/designer?model=crm.lead&type=form");
  m.compile.mockReset().mockImplementation(async () => compiled());
  m.commentsList.mockReset().mockResolvedValue({ comments: [] });
  m.historyList.mockReset().mockResolvedValue({ versions: [] });
  m.fieldImpact.mockReset();
  m.previewAs.mockReset();
  m.command.mockReset();
  toast.mockClear();
  toast.success.mockClear();
});
afterEach(() => cleanup());

async function openDesigner() {
  render(<ViewDesignerShell connectionId="c1" />);
  await waitFor(() => expect(screen.getByTestId("vd-canvas")).toBeInTheDocument());
}
const canvasNode = (id: string) => document.querySelector(`[data-node-id="${id}"]`) as HTMLElement;

describe("View Designer stage 2a", () => {
  it("shift-click picks several fields and applies the same roles to all after a plain impact preview", async () => {
    m.fieldImpact.mockResolvedValue({
      impact: ["3 people lose sight of Phone: A, B and C."], blocks: [], warnings: [], lose: [], gain: [],
      op: { op: "set_access", node: "field:phone", edit: ["sales_team.group_sale_manager"], see: [] },
    });
    await openDesigner();
    fireEvent.click(canvasNode("field:phone"));
    fireEvent.click(canvasNode("field:mobile"), { shiftKey: true });
    expect(screen.getByTestId("vd-multi")).toHaveTextContent("2 items selected");
    const who = screen.getByTestId("vd-who");
    fireEvent.change(within(who).getByLabelText("Limit to a role"), { target: { value: "admin" } });
    fireEvent.click(within(who).getByRole("button", { name: /Sales \/ Administrator/ }));
    await waitFor(() => expect(screen.getByTestId("vd-impact")).toHaveTextContent("3 people lose sight of Phone"));
    expect(m.fieldImpact.mock.calls[0][2]).toEqual({ node: "field:phone", edit: ["sales_team.group_sale_manager"], see: [], also: ["field:mobile"] });
    fireEvent.click(within(who).getByRole("button", { name: "Use these roles" }));
    await waitFor(() => expect(m.compile).toHaveBeenCalled());
    expect(m.compile.mock.calls.at(-1)?.[3]).toEqual([
      { op: "set_access", node: "field:phone", edit: ["sales_team.group_sale_manager"], see: [] },
      { op: "set_access", node: "field:mobile", edit: ["sales_team.group_sale_manager"], see: [] },
    ]);
    expect(toast).toHaveBeenCalledWith("Changed who can see 2 items", expect.objectContaining({ action: expect.objectContaining({ label: "Undo" }) }));
  });

  it("blocks the change when the preview finds a lockout", async () => {
    m.fieldImpact.mockResolvedValue({
      impact: [], warnings: [], lose: [], gain: [], op: {},
      blocks: ["Administrators (Mitchell Admin) would lose sight of Phone. Add the role 'Settings' or choose Everyone."],
    });
    await openDesigner();
    fireEvent.click(canvasNode("field:phone"));
    const who = screen.getByTestId("vd-who");
    fireEvent.change(within(who).getByLabelText("Limit to a role"), { target: { value: "user" } });
    fireEvent.click(within(who).getByRole("button", { name: /Sales \/ User/ }));
    await waitFor(() => expect(within(who).getByRole("alert")).toHaveTextContent("Administrators"));
    expect(within(who).getByRole("button", { name: "Use these roles" })).toBeDisabled();
  });

  it("Odoo 17: when roles can't be limited, one click opens a hide rule on the field", async () => {
    m.fieldImpact.mockResolvedValue({
      impact: [], warnings: [], lose: [], gain: [], op: {},
      blocks: ["On Odoo 17, other parts of this screen use Phone, so Odoo won't let it be limited to some roles."],
      alternative: { kind: "rule", node: "field:phone", nodes: ["field:phone"], attr: "invisible", sense: "hide", label: "Use a show/hide rule instead" },
    });
    await openDesigner();
    fireEvent.click(canvasNode("field:phone"));
    const who = screen.getByTestId("vd-who");
    fireEvent.change(within(who).getByLabelText("Limit to a role"), { target: { value: "user" } });
    fireEvent.click(within(who).getByRole("button", { name: /Sales \/ User/ }));
    fireEvent.click(await screen.findByTestId("vd-use-rule"));
    await waitFor(() => expect((within(screen.getByTestId("vd-rules")).getByLabelText("Show or hide") as HTMLSelectElement).value).toBe("hide"));
  });

  it("turns a sentence into a rule the server wrote, and applies the reading picked", async () => {
    m.conditionWords.mockResolvedValue({
      readings: [{ sense: "show", condition: { match: "all", rules: [{ field: "stage_id", op: "is", value: 4 }] }, sentence: "Stage is Won", rule_sentence: "Shown only when Stage is Won", expression: "stage_id == 4" }],
      unclear: null,
    });
    await openDesigner();
    fireEvent.click(canvasNode("field:email"));
    const rules = screen.getByTestId("vd-rules");
    expect(within(rules).getByTestId("vd-rule-now")).toHaveTextContent("Hidden when Is a company is not ticked");
    fireEvent.change(within(rules).getByLabelText("Describe it"), { target: { value: "Show when Stage is Won" } });
    fireEvent.click(within(rules).getByRole("button", { name: "Turn into a rule" }));
    await waitFor(() => expect(within(rules).getByText("Shown only when Stage is Won")).toBeInTheDocument());
    fireEvent.click(within(rules).getByRole("button", { name: "Use this" }));
    await waitFor(() => expect(m.compile).toHaveBeenCalled());
    expect(m.compile.mock.calls.at(-1)?.[3]).toEqual([
      { op: "set_condition", node: "field:email", attr: "invisible", sense: "show", condition: { match: "all", rules: [{ field: "stage_id", op: "is", value: 4 }] }, keep_existing: true },
    ]);
  });

  it("previews a role: hidden items say why on hover", async () => {
    m.previewAs.mockResolvedValue({
      who: { kind: "role", name: "Sales / User" },
      visibility: { "field:phone": { visible: false, reason: "Only Sales / Administrator can see it." } },
      also_sees: [], perms: { read: true, write: true, create: true, unlink: false },
      summary: "Sales / User can open, change and create Lead. 1 field is hidden for them on this screen.",
      read_only: false, based_on: "Based on group rules.",
    });
    await openDesigner();
    fireEvent.change(screen.getByTestId("vd-preview-role"), { target: { value: "sales_team.group_sale_salesman" } });
    await waitFor(() => expect(screen.getByTestId("vd-preview-summary")).toHaveTextContent("1 field is hidden"));
    const why = within(canvasNode("field:phone")).getByTestId("vd-why-hidden");
    expect(why).toHaveTextContent("Hidden for this role");
    fireEvent.focus(why);
    fireEvent.mouseEnter(why);
    await waitFor(() => expect(screen.getAllByText("Only Sales / Administrator can see it.").length).toBeGreaterThan(0));
  });

  it("⌘K describes a change: AI proposes, the screen marks it, Apply adds the checked ops", async () => {
    m.command.mockResolvedValue({ ops: [{ op: "hide", node: "field:mobile" }], unclear: null, descriptions: ["Hide Mobile"], markers: { "field:mobile": "hidden" } });
    await openDesigner();
    fireEvent.keyDown(window, { key: "k", metaKey: true });
    const bar = await screen.findByTestId("vd-command");
    fireEvent.change(within(bar).getByPlaceholderText(/describe a change/), { target: { value: "hide the mobile number" } });
    fireEvent.click(await within(bar).findByText(/Make this change/));
    await waitFor(() => expect(within(bar).getByText("Hide Mobile")).toBeInTheDocument());
    expect(canvasNode("field:mobile").getAttribute("data-marker")).toBe("hidden");
    fireEvent.click(within(bar).getByRole("button", { name: /^Apply \d+ changes?$/ }));
    await waitFor(() => expect(m.compile.mock.calls.at(-1)?.[3]).toEqual([{ op: "hide", node: "field:mobile" }]));
    expect(screen.queryByTestId("vd-command")).toBeNull();
  });

  it("C shows pinned comment dots; ⌘⏎ sends a comment on the selected field", async () => {
    m.commentsList.mockResolvedValue({ comments: [{ id: "k1", node_id: "field:phone", parent_id: null, author: "Tope", body: "Check this", resolved: false, created_at: null, resolved_at: null }] });
    m.commentsAdd.mockResolvedValue({});
    await openDesigner();
    fireEvent.keyDown(window, { key: "c" });
    const dot = await screen.findByRole("button", { name: /1 open comment on Phone/ });
    fireEvent.click(dot);
    const panel = await screen.findByTestId("vd-comments");
    expect(within(panel).getByTestId("vd-thread")).toHaveTextContent("Check this");
    const box = within(panel).getByLabelText("New comment");
    fireEvent.change(box, { target: { value: "Looks good" } });
    fireEvent.keyDown(box, { key: "Enter", metaKey: true });
    await waitFor(() => expect(m.commentsAdd).toHaveBeenCalledWith("c1", { model: "crm.lead", view_type: "form", node_id: "field:phone", body: "Looks good", parent_id: null }));
  });

  it("history: compare marks the canvas; the scrubber shows an earlier version read-only", async () => {
    m.historyList.mockResolvedValue({
      versions: [
        { id: "v2", action: "publish", label: null, summary: ["Moved Phone"], layer_active: true, has_layer: true, created_at: "2026-10-15T12:00:00Z", odoo_major: 18, layer_view_id: 9 },
        { id: "v1", action: "publish", label: "Before launch", summary: [], layer_active: false, has_layer: true, created_at: "2026-10-14T12:00:00Z", odoo_major: 18, layer_view_id: 9 },
      ],
    });
    m.historyCompare.mockResolvedValue({ from_tree: tree, to_tree: tree, markers: { "field:phone": "moved" }, changes: ["Moved Phone"] });
    m.historyTree.mockResolvedValue({ version: {}, tree: n("root", "form", [n("field:old", "field", [], { label: "Old" })], { kind: "root" }) });
    await openDesigner();
    fireEvent.click(screen.getByRole("tab", { name: "History" }));
    const rows = await screen.findAllByTestId("vd-history-row");
    expect(rows[1]).toHaveTextContent("Before launch");
    fireEvent.click(within(rows[1]).getByRole("button", { name: "Compare with now" }));
    await waitFor(() => expect(canvasNode("field:phone").getAttribute("data-marker")).toBe("moved"));
    expect(screen.getByText("1 moved")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("slider"), { target: { value: "0" } });
    await waitFor(() => expect(screen.getByTestId("vd-scrub-banner")).toHaveTextContent("Before launch"));
    expect(canvasNode("field:old")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Back to now" }));
    expect(canvasNode("field:phone")).toBeTruthy();
  });

  it("record-type access: preview in plain words, apply, and an Undo toast", async () => {
    m.modelAccess.mockResolvedValue({
      model: "crm.lead", label: "Lead", rows: [], everyone: null, editable: true, rules_link: "/connections/c1/access?model=crm.lead",
      roles: [{ group: "sales_team.group_sale_salesman", name: "Sales / User", perms: { read: true, write: true, create: true, unlink: false }, people: 3 }],
      rules: [{ id: 1, name: "Personal Leads", applies_to: "Sales / User", domain: "", plain: "Salesperson is the person themself", perms: ["read"] }],
    });
    m.modelAccessPreview.mockResolvedValue({ impact: ["3 people can now delete Lead: A, B and C."], blocks: [], actions: 1 });
    m.modelAccessApply.mockResolvedValue({ ok: true, impact: ["3 people can now delete Lead: A, B and C."], undo: [{ type: "delete", id: 5 }] });
    await openDesigner();
    fireEvent.click(screen.getByRole("button", { name: "Access to this record type…" }));
    const sheet = await screen.findByTestId("vd-record-access");
    expect(within(sheet).getByText(/Salesperson is the person themself/)).toBeInTheDocument();
    fireEvent.click(within(sheet).getByLabelText("Sales / User: Delete"));
    await waitFor(() => expect(within(sheet).getByText("3 people can now delete Lead: A, B and C.")).toBeInTheDocument());
    fireEvent.click(within(sheet).getByRole("button", { name: "Apply access changes" }));
    await waitFor(() => expect(m.modelAccessApply).toHaveBeenCalledWith("c1", "crm.lead", [{ group: "sales_team.group_sale_salesman", read: true, write: true, create: true, unlink: true }]));
    expect(toast.success).toHaveBeenCalledWith("3 people can now delete Lead: A, B and C.", expect.objectContaining({ action: expect.objectContaining({ label: "Undo" }) }));
  });

  it("device preview narrows the screen", async () => {
    await openDesigner();
    fireEvent.click(screen.getByRole("button", { name: "Phone" }));
    const dev = document.querySelector("[data-device]") as HTMLElement;
    expect(dev.getAttribute("data-device")).toBe("phone");
    expect(dev.style.maxWidth).toBe("390px");
    await act(async () => undefined);
  });
});
