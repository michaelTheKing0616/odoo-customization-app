import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LiveDatabaseSection } from "../LiveDatabaseSection";
import { accessSpec, automationSpec, overlayBody } from "./stock-specs";

const m = {
  getLiveSnapshot: vi.fn(), getSnapshotModel: vi.fn(), applyModuleSpec: vi.fn(), listModules: vi.fn(),
  overlayPreview: vi.fn(), applyOverlayOp: vi.fn(), listMenuTree: vi.fn(), createWindowAction: vi.fn(),
  createBuilderMenu: vi.fn(), getExtensionScaffold: vi.fn(), exportCodeStudioOptionA: vi.fn(), runSandbox: vi.fn(),
  promoteModule: vi.fn(), createField: vi.fn(), updateField: vi.fn(),
};
vi.mock("@/lib/api", () => ({
  api: new Proxy({}, { get: (_t, k: string) => (...a: unknown[]) => (m as Record<string, (...x: unknown[]) => unknown>)[k](...a) }),
}));

const ALL = ["custom_fields", "xpath_inherit", "base_automation", "security_acl_rules", "menus_actions", "python_module_install"];
const caps = (locked: string[] = []) => ALL.map((key) => ({
  key, available: locked.includes(key) ? "no" : "yes",
  reason: locked.includes(key) ? "Odoo Online doesn't allow custom Python code." : "",
}));
const snap = (locked: string[] = []) => ({
  ok: true, major: 19, series: "19.0", server_version: "19.0", edition: "community", hosting: locked.length ? "online" : "sh", support: "supported",
  apps: [], modules: [], counts: { modules: 1, modules_hidden: 0, apps: 0, models: 1, custom_models: 0, automations: 0, scheduled_actions: 0, groups: 0 },
  custom_models: [], models: [{ model: "res.partner", label: "Contact" }], automations: [], scheduled_actions: [], groups: [],
  can_change: caps(locked), problems: [], attention: [],
});
const f = (o: Record<string, unknown>) => ({ type: "char", string: "", required: false, relation: "", selection: [], custom: false, id: null, help: "", ...o });
const PARTNER = {
  model: "res.partner", label: "Contact", custom: false,
  fields: [f({ name: "email", string: "Email" }), f({ name: "phone", string: "Phone" }), f({ name: "x_tier", string: "Tier", custom: true, id: 7 }),
    f({ name: "type", string: "Address type", type: "selection", selection: ["contact", "invoice"] }),
    f({ name: "user_id", string: "Salesperson", type: "many2one", relation: "res.users" }), f({ name: "date", string: "Date", type: "date" })],
  views: { types: ["form", "list"], form_field_count: 2, form_fields: ["email", "phone"] }, server_actions: [], menus: [],
  record_rules: { source: "ir.model.access", rows: [] }, problems: [],
};

afterEach(() => { cleanup(); vi.clearAllMocks(); window.history.replaceState(null, "", "/"); });

async function openPartner(locked: string[] = []) {
  m.getLiveSnapshot.mockResolvedValue(snap(locked));
  m.getSnapshotModel.mockResolvedValue(PARTNER);
  render(<LiveDatabaseSection connectionId="c1" />);
  fireEvent.click(await screen.findByRole("option", { name: /Contact/ }));
  await screen.findByTestId("tab-fields");
}
const tab = (name: RegExp) => fireEvent.click(screen.getByRole("tab", { name }));

describe("Extending Odoo's own models from Overview", () => {
  it("says plainly that built-in fields and screens are never edited in place", async () => {
    await openPartner();
    expect(screen.getByTestId("tab-fields")).toHaveTextContent("Odoo's own fields can't be changed in place");
    expect(screen.queryByRole("button", { name: "Edit Email" })).toBeNull();
    tab(/Views/);
    expect(await screen.findByTestId("stock-views-note")).toHaveTextContent("never edited in place");
  });

  it("extends the form through an extension view: preview first, then Apply", async () => {
    m.overlayPreview.mockResolvedValue({ xpath_arch: "<data><xpath expr=\"//field[@name='phone']\" position=\"after\"><field name=\"x_tier\"/></xpath></data>", issues: [] });
    m.applyOverlayOp.mockResolvedValue({ view_id: 3, inherit_name: "res.partner.overlay.form", xpath_arch: "", issues: [] });
    await openPartner();
    tab(/Views/);
    fireEvent.click(await screen.findByTestId("extend-view-btn"));
    fireEvent.change(screen.getByLabelText("Field"), { target: { value: "x_tier" } });
    fireEvent.click(screen.getByTestId("extend-view-preview-btn"));
    expect(await screen.findByTestId("change-summary")).toHaveTextContent("Show “Tier” after “Phone”");
    expect(m.applyOverlayOp).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId("apply"));
    await waitFor(() => expect(m.applyOverlayOp).toHaveBeenCalledWith("c1", expect.objectContaining({
      model: "res.partner", view_type: "form", operation: "add_field", add_field_name: "x_tier", expr: "(//field[@name='phone'])[1]" })));
    await waitFor(() => expect(m.getLiveSnapshot).toHaveBeenCalledWith("c1", { refresh: true }));
  });

  it("adds access rights limited to own records through the shared Apply", async () => {
    m.applyModuleSpec.mockResolvedValue({ ok: true });
    await openPartner();
    tab(/Rules/);
    fireEvent.click(await screen.findByTestId("add-access-btn"));
    fireEvent.click(screen.getByLabelText("Edit"));
    fireEvent.click(screen.getByLabelText("Only records they created"));
    fireEvent.click(screen.getByTestId("access-review"));
    expect(screen.getByTestId("change-summary")).toHaveTextContent("Internal users can read, edit");
    fireEvent.click(screen.getByTestId("apply"));
    await waitFor(() => expect(m.applyModuleSpec).toHaveBeenCalled());
    const rule = m.applyModuleSpec.mock.calls[0][1].spec.access_rules[0];
    expect(rule).toMatchObject({ model: "res.partner", group: "base.group_user", perm_write: true, perm_unlink: false, domain: "[('create_uid', '=', user.id)]" });
  });

  it("adds a dated automation with a responsible user", async () => {
    m.applyModuleSpec.mockResolvedValue({ ok: true });
    await openPartner();
    tab(/Actions/);
    fireEvent.click(await screen.findByTestId("add-automation-btn"));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Call back" } });
    fireEvent.change(screen.getByLabelText("When"), { target: { value: "date" } });
    fireEvent.click(screen.getByTestId("automation-review"));
    expect(screen.getByTestId("change-summary")).toHaveTextContent("1 day before Date (checked by a scheduled action)");
    fireEvent.click(screen.getByTestId("apply"));
    await waitFor(() => expect(m.applyModuleSpec).toHaveBeenCalledWith("c1", expect.objectContaining({ apply_automations: true })));
    const auto = m.applyModuleSpec.mock.calls[0][1].spec.automations[0];
    expect(auto).toMatchObject({ model: "res.partner", trigger: "on_time", trg_date_field_name: "date",
      safe_actions: [{ kind: "next_activity", user_type: "generic", activity_user_field_name: "user_id" }] });
  });

  it("adds a menu under the chosen app", async () => {
    m.listMenuTree.mockResolvedValue([{ id: 5, name: "Sales" }, { id: 6, name: "Contacts" }]);
    m.createWindowAction.mockResolvedValue({ id: 40, name: "Contact", res_model: "res.partner" });
    m.createBuilderMenu.mockResolvedValue({ id: 41 });
    await openPartner();
    tab(/Menus/);
    fireEvent.click(await screen.findByTestId("add-menu-btn"));
    fireEvent.change(await screen.findByLabelText("Under app"), { target: { value: "6" } });
    fireEvent.click(screen.getByTestId("menu-review"));
    expect(screen.getByTestId("change-summary")).toHaveTextContent("Add “Contact” under Contacts");
    fireEvent.click(screen.getByTestId("apply"));
    await waitFor(() => expect(m.createBuilderMenu).toHaveBeenCalledWith("c1", { name: "Contact", parent_id: 6, action_id: 40 }));
    expect(m.createWindowAction).toHaveBeenCalledWith("c1", { name: "Contact", model: "res.partner", view_mode: "list,form" });
  });

  it("custom code: draft, test on a test copy, then one Publish button", async () => {
    m.getExtensionScaffold.mockResolvedValue({ code: "class X: _inherit = 'res.partner'", depends: ["base"], technical_name: "res_partner_extension" });
    m.exportCodeStudioOptionA.mockResolvedValue({ technical_name: "res_partner_extension", content_base64: "Wklw" });
    m.runSandbox.mockResolvedValue({ ok: true, message: "", validation_id: "v1" });
    m.promoteModule.mockResolvedValue({ ok: true, message: "Published." });
    await openPartner();
    fireEvent.click(screen.getByTestId("extend-code-btn"));
    fireEvent.change(screen.getByLabelText("New options"), { target: { value: "branch: Branch" } });
    fireEvent.click(screen.getByTestId("code-draft"));
    await screen.findByTestId("code-draft-text");
    expect(m.getExtensionScaffold).toHaveBeenCalledWith("c1", expect.objectContaining({ kind: "selection_options", field_name: "type", options: [{ value: "branch", label: "Branch" }] }));
    expect(screen.queryByTestId("code-publish")).toBeNull();
    fireEvent.click(screen.getByTestId("code-test"));
    await screen.findByTestId("code-tested");
    expect(m.exportCodeStudioOptionA).toHaveBeenCalledWith("c1", expect.objectContaining({ as_extension: true, depends: ["base"] }));
    expect(m.promoteModule).not.toHaveBeenCalled();
    expect(screen.queryByTestId("code-test")).toBeNull();
    fireEvent.click(screen.getByTestId("code-publish"));
    await waitFor(() => expect(m.promoteModule).toHaveBeenCalledWith("c1", expect.objectContaining({ validation_id: "v1", zip_base64: "Wklw" })));
  });

  it("shows each locked change with its reason instead of hiding it", async () => {
    await openPartner(["python_module_install", "base_automation"]);
    expect(screen.getByTestId("extend-code-locked")).toHaveTextContent("Odoo Online doesn't allow custom Python code.");
    expect(screen.queryByTestId("extend-code-btn")).toBeNull();
    tab(/Actions/);
    expect(await screen.findByTestId("add-automation-btn-locked")).toHaveTextContent("Add automation rule isn't available here");
  });

  it("builds bodies that never target the original arch", () => {
    expect(overlayBody({ model: "res.partner", viewType: "list", op: "add", field: "x_tier", after: "" }))
      .toMatchObject({ operation: "add_field", expr: "/*", add_position: "inside" });
    expect(overlayBody({ model: "res.partner", viewType: "form", op: "move", field: "phone", after: "email" }))
      .toMatchObject({ operation: "move", expr: "(//field[@name='phone'])[1]", anchor_expr: "(//field[@name='email'])[1]" });
    expect(accessSpec({ model: "res.partner", group: "base.group_user", read: true, write: false, create: false, remove: false, ownOnly: false }).access_rules)
      .toEqual([expect.not.objectContaining({ domain: expect.anything() })]);
    expect(automationSpec({ model: "res.partner", name: "x", when: "created", action: "set", setField: "comment", setValue: "hi" }).automations)
      .toEqual([expect.objectContaining({ trigger: "on_create", safe_actions: [{ kind: "update_field", field_name: "comment", value: "hi" }] })]);
  });
});
