import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LiveDatabaseSection } from "../LiveDatabaseSection";
import { parseOptions, selectionLiteral } from "./gates";

const m = {
  getLiveSnapshot: vi.fn(), getSnapshotModel: vi.fn(), createField: vi.fn(), updateField: vi.fn(),
  applyModuleSpec: vi.fn(), listModules: vi.fn(), installCommunityModule: vi.fn(),
};
vi.mock("@/lib/api", () => ({
  api: new Proxy({}, { get: (_t, k: string) => (...a: unknown[]) => (m as Record<string, (...x: unknown[]) => unknown>)[k](...a) }),
}));

const caps = (over: Record<string, string> = {}) =>
  Object.entries({ custom_fields: "yes", security_acl_rules: "yes", menus_actions: "yes", python_module_install: "yes", ...over })
    .map(([key, available]) => ({ key, available, reason: available === "yes" ? "" : "Odoo Online doesn't allow custom Python code." }));

const SNAP = {
  ok: true, major: 18, series: "18.0", server_version: "18.0", edition: "community", hosting: "onprem", support: "supported",
  apps: [{ name: "sale", label: "Sales" }], modules: [],
  counts: { modules: 4, modules_hidden: 0, apps: 1, models: 2, custom_models: 1, automations: 0, scheduled_actions: 0, groups: 1 },
  custom_models: [{ model: "x_renewal", label: "Renewal" }],
  models: [{ model: "res.partner", label: "Contact" }, { model: "x_renewal", label: "Renewal" }],
  automations: [], scheduled_actions: [], groups: [], can_change: caps(), problems: [], attention: [] as unknown[],
};
const field = (o: Record<string, unknown>) => ({ type: "char", string: "", required: false, relation: "", selection: [], readonly: false, stored: true, custom: false, id: null, help: "", ...o });
const DETAIL = {
  model: "x_renewal", label: "Renewal", custom: true,
  fields: [field({ name: "x_note", string: "Note", custom: true, id: 41, help: "Old help" }), field({ name: "create_date", string: "Created on", type: "datetime" })],
  views: { types: ["form"], form_field_count: 1, form_fields: [] }, server_actions: [], menus: [],
  record_rules: { source: "ir.model.access", rows: [] }, problems: [],
};

afterEach(() => { cleanup(); vi.clearAllMocks(); window.history.replaceState(null, "", "/"); });

async function openRenewal(snap = SNAP) {
  m.getLiveSnapshot.mockResolvedValue(snap);
  m.getSnapshotModel.mockResolvedValue(DETAIL);
  render(<LiveDatabaseSection connectionId="c1" />);
  fireEvent.click(await screen.findByRole("option", { name: /Renewal/ }));
  return screen.findByTestId("tab-fields");
}

describe("Overview editing", () => {
  it("adds a field via preview-then-Apply, then reloads the snapshot and the model", async () => {
    m.createField.mockResolvedValue({ id: 99 });
    await openRenewal();
    fireEvent.click(screen.getByTestId("add-field"));
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Owner note" } });
    fireEvent.click(screen.getByRole("button", { name: "Review change" }));
    expect(screen.getByTestId("change-summary")).toHaveTextContent("Add “Owner note” (Short text) to Renewal, as x_owner_note");
    expect(m.createField).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("apply"));
    await waitFor(() => expect(m.createField).toHaveBeenCalledWith("c1", expect.objectContaining({
      model: "x_renewal", name: "x_owner_note", field_description: "Owner note", ttype: "char", inject_into_views: true })));
    await waitFor(() => expect(m.getLiveSnapshot).toHaveBeenCalledWith("c1", { refresh: true }));
    expect(m.getSnapshotModel).toHaveBeenCalledWith("c1", "x_renewal", { refresh: true });
  });

  it("edits only custom fields, and shows Odoo's error honestly", async () => {
    m.updateField.mockRejectedValueOnce(new Error("Field is required somewhere.")).mockResolvedValue({});
    await openRenewal();
    expect(screen.getAllByRole("button", { name: /^Edit / })).toHaveLength(1); // stock create_date has no Edit
    fireEvent.click(screen.getByRole("button", { name: "Edit Note" }));
    fireEvent.change(screen.getByLabelText("Label"), { target: { value: "Renewal note" } });
    fireEvent.click(screen.getByLabelText("Required"));
    fireEvent.click(screen.getByRole("button", { name: "Review change" }));
    const summary = screen.getByTestId("change-summary");
    expect(summary).toHaveTextContent("Rename “Note” to “Renewal note”");
    expect(summary).toHaveTextContent("Make it required");
    fireEvent.click(screen.getByTestId("apply"));
    expect(await screen.findByTestId("apply-error")).toHaveTextContent("Field is required somewhere.");
    fireEvent.click(screen.getByTestId("apply"));
    await waitFor(() => expect(m.updateField).toHaveBeenLastCalledWith("c1", 41, { field_description: "Renewal note", required: true, help: "Old help" }));
  });

  it("locked actions say why instead of disappearing", async () => {
    await openRenewal({ ...SNAP, can_change: caps({ custom_fields: "no", python_module_install: "no" }) });
    expect(screen.queryByTestId("add-field")).toBeNull();
    expect(screen.getByTestId("add-field-locked")).toHaveTextContent("Adding fields isn't available here.");
    expect(screen.getByTestId("custom-code-locked")).toHaveTextContent("Odoo Online doesn't allow custom Python code.");
    expect(screen.queryByTestId("build-custom-code")).toBeNull();
  });

  it("custom code and Designer entries link into the existing flows", async () => {
    await openRenewal();
    expect(screen.getByTestId("build-custom-code")).toHaveAttribute("href", "/connections/c1/code-studio");
    fireEvent.click(screen.getByRole("tab", { name: /Views/ }));
    expect(await screen.findByTestId("open-designer")).toHaveAttribute("href", "/connections/c1/designer?model=x_renewal");
  });

  it("attention items get a direct fix through the same preview-then-Apply", async () => {
    m.applyModuleSpec.mockResolvedValue({ ok: true });
    m.getLiveSnapshot.mockResolvedValue({ ...SNAP, attention: [
      { key: "custom_no_access", severity: "warning", rank: 2, title: "Custom models nobody can open", detail: "", count: 1,
        drill: { section: "explorer", model: "x_renewal", tab: "rules" }, names: ["x_renewal"] }] });
    render(<LiveDatabaseSection connectionId="c1" />);
    fireEvent.click(await screen.findByTestId("fix-custom_no_access"));
    expect(screen.getByTestId("change-summary")).toHaveTextContent("Let internal users read, create and edit Renewal records");
    fireEvent.click(screen.getByTestId("apply"));
    await waitFor(() => expect(m.applyModuleSpec).toHaveBeenCalled());
    const body = m.applyModuleSpec.mock.calls[0][1];
    expect(body.spec.access_rules[0]).toMatchObject({ model: "x_renewal", group: "base.group_user", perm_unlink: false });
    expect(body.apply_menus).toBe(false);
    await waitFor(() => expect(m.getLiveSnapshot).toHaveBeenCalledWith("c1", { refresh: true }));
  });

  it("no fix button when the plan doesn't allow it (the item still drills down)", async () => {
    m.getLiveSnapshot.mockResolvedValue({ ...SNAP, can_change: caps({ menus_actions: "no" }), attention: [
      { key: "custom_no_menu", severity: "warning", rank: 2, title: "Custom models without a menu", detail: "", count: 1,
        drill: { section: "explorer", model: "x_renewal", tab: "menus" }, names: ["x_renewal"] }] });
    render(<LiveDatabaseSection connectionId="c1" />);
    await screen.findByTestId("attention");
    expect(screen.queryByTestId("fix-custom_no_menu")).toBeNull();
    expect(screen.getByRole("button", { name: /Open model/ })).toBeInTheDocument();
  });

  it("installs an available stock app after confirmation", async () => {
    m.listModules.mockResolvedValue([
      { id: 1, name: "crm", shortdesc: "CRM", state: "uninstalled", application: true },
      { id: 2, name: "sale", shortdesc: "Sales", state: "installed", application: true },
    ]);
    m.installCommunityModule.mockResolvedValue({ ok: true });
    m.getLiveSnapshot.mockResolvedValue(SNAP);
    render(<LiveDatabaseSection connectionId="c1" />);
    fireEvent.click(await screen.findByTestId("add-app"));
    const list = await screen.findByTestId("app-list");
    expect(list).not.toHaveTextContent("Sales");
    fireEvent.click(within(list).getByRole("button", { name: "Install" }));
    expect(m.installCommunityModule).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("install-confirm-yes"));
    await waitFor(() => expect(m.installCommunityModule).toHaveBeenCalledWith("c1", "crm"));
    await waitFor(() => expect(m.getLiveSnapshot).toHaveBeenCalledWith("c1", { refresh: true }));
  });

  it("selection helpers build Odoo's literal safely", () => {
    const opts = parseOptions("new: New\nIn progress\nlost: Lost 'cold'");
    expect(opts).toEqual([{ value: "new", label: "New" }, { value: "in_progress", label: "In progress" }, { value: "lost", label: "Lost 'cold'" }]);
    expect(selectionLiteral(opts)).toBe("[('new', 'New'), ('in_progress', 'In progress'), ('lost', 'Lost \\'cold\\'')]");
  });
});
