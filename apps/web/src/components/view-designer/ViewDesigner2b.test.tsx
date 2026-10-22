import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { EngineNode } from "@/lib/api/view-engine";

const n = (id: string, tag: string, children: EngineNode[] = [], extra: Partial<EngineNode> = {}): EngineNode => ({
  id, tag, kind: tag === "field" ? "field" : "container", name: id.split(":")[1] ?? null, label: id.split(":")[1] ?? tag, attrs: {},
  anchor: `//${tag}[@name='${id.split(":")[1]}']`, locked_reason: null, children, ...extra,
});
const tree = n("root", "form", [n("sheet:s", "sheet", [n("group:a", "group", [n("field:name", "field")])])], { kind: "root" });

const m = vi.hoisted(() => ({
  checks: vi.fn(),
  tidy: vi.fn(),
  library: vi.fn(),
  packageCheck: vi.fn(),
  packageImport: vi.fn(),
  sections: vi.fn(),
}));
vi.mock("@/lib/api", () => ({
  api: {
    checks: (...a: unknown[]) => m.checks(...a),
    tidy: (...a: unknown[]) => m.tidy(...a),
    library: (...a: unknown[]) => m.library(...a),
    sectionList: (...a: unknown[]) => m.sections(...a),
    packageCheck: (...a: unknown[]) => m.packageCheck(...a),
    packageImport: (...a: unknown[]) => m.packageImport(...a),
    packageExport: vi.fn(),
    screenTemplates: vi.fn(async () => ({ templates: [], screens: [] })),
  },
}));
const toast = vi.hoisted(() => Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn() }));
vi.mock("sonner", () => ({ toast }));

import { BuilderSheet } from "./BuilderSheet";
import { BuildPanel } from "./BuildPanel";
import { ChecksPanel } from "./ChecksPanel";
import { ScreenSettings } from "./ItemExtras";

const errorText = (e: unknown) => String(e);
beforeEach(() => {
  Object.values(m).forEach((f) => f.mockReset());
  m.sections.mockResolvedValue({ sections: [] });
  toast.mockClear();
  toast.success.mockClear();
});
afterEach(() => cleanup());

describe("View Designer stage 2b", () => {
  it("Checks: shows the health score and Fix all sends each fix once", async () => {
    const fixA = { op: "set_attr", node: "field:name", attr: "string", value: "Name" };
    m.checks.mockResolvedValue({
      health: { score: 72, parts: [] },
      issues: [
        { kind: "no_label", node: "field:name", text: "Name has no label", fix_label: "Add a label", ops: [fixA] },
        { kind: "no_label", node: "field:name", text: "Duplicate", fix_label: "Add a label", ops: [fixA] },
      ],
      suggestions: [], performance: [], total: 2,
    });
    const onOps = vi.fn();
    render(<ChecksPanel connectionId="c1" model="res.partner" viewType="form" viewId={null} ops={[]} onOps={onOps} onJump={vi.fn()} errorText={errorText} />);
    await waitFor(() => expect(screen.getByTestId("vd-health")).toHaveTextContent("72"), { timeout: 2000 });
    fireEvent.click(screen.getAllByRole("button", { name: "Fix all" })[0]);
    expect(onOps).toHaveBeenCalledWith([fixA], expect.stringContaining("Fix all"));
  });

  it("Add: a header goes before the sheet; a status bar without a header explains why not", async () => {
    m.library.mockResolvedValue({
      major: 18, root_tag: "form", field_types: [], existing_fields: [],
      layout: [{ kind: "header", label: "Header bar" }], buttons: [{ kind: "statusbar", label: "Status bar" }],
    });
    const onOps = vi.fn();
    render(<BuildPanel connectionId="c1" model="res.partner" viewType="form" viewId={null} ops={[]} tree={tree} selected={null} onOps={onOps} onFieldsChanged={vi.fn()} errorText={errorText} />);
    fireEvent.click(await screen.findByTestId("vd-el-header"));
    expect(onOps).toHaveBeenCalledWith([expect.objectContaining({ op: "insert_element", element: "header", target: "sheet:s", position: "before" })], "Add header bar");
  });

  it("Saved section: fields already on the screen are left out and named", async () => {
    m.library.mockResolvedValue({
      major: 18, root_tag: "form", field_types: [], layout: [], buttons: [],
      existing_fields: [{ name: "name", label: "Name", type: "char", on_screen: true, widgets: [] }, { name: "phone", label: "Phone", type: "char", on_screen: false, widgets: [] }],
    });
    m.sections.mockResolvedValue({ sections: [{ id: "s1", kind: "section", key: "res.partner", name: "Contact bits", created_at: "", fit: { fits: true, missing: [], wrong_type: [] },
      payload: { xml: "<group><field name='name'/><field name='phone'/></group>", tag: "group", model: "res.partner",
        fields: [{ name: "name", type: "char", label: "Name" }, { name: "phone", type: "char", label: "Phone" }] } }] });
    const onOps = vi.fn();
    render(<BuildPanel connectionId="c1" model="res.partner" viewType="form" viewId={null} ops={[]} tree={tree} selected={null} onOps={onOps} onFieldsChanged={vi.fn()} errorText={errorText} />);
    expect(await screen.findByText(/1 already on this screen \(left out\)/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Insert" }));
    expect(onOps).toHaveBeenCalledWith([expect.objectContaining({ op: "insert_section", skip: ["name"] })], "Insert section Contact bits");
    expect(toast).toHaveBeenCalledWith(expect.stringContaining("Left out 1 field already on this screen or not on this record type: Name."));
  });

  it("Card settings: the colour flag sends one of Odoo's card colours", () => {
    const onOp = vi.fn();
    const kanban = n("root", "kanban", [], { kind: "root" });
    render(
      <ScreenSettings root={kanban} connectionId="c1" model="crm.lead" viewType="kanban" viewId={null}
        fields={{ priority: { string: "Priority", type: "selection" } }} onOp={onOp} onOps={vi.fn()} errorText={errorText} />,
    );
    const flag = screen.getByLabelText("Flag colour") as HTMLSelectElement;
    expect([...flag.options].map((o) => o.value)).toEqual(["danger", "warning", "success", "info", "muted", "primary"]);
    fireEvent.change(flag, { target: { value: "info" } });
    const forms = screen.getAllByLabelText("When field");
    fireEvent.change(forms[forms.length - 1], { target: { value: "priority" } });
    fireEvent.change(screen.getAllByLabelText("Value").at(-1)!, { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Colour flag when" }));
    expect(onOp).toHaveBeenCalledWith({ op: "kanban_add", kind: "colour", condition: { match: "all", rules: [{ field: "priority", op: "is", value: "3" }] }, props: { style: "info" } });
  });

  it("Package import: checks the file, warns it replaces changes here, then imports with replace", async () => {
    const pkg = { format: "ingenium-layout/1", model: "res.partner", view_type: "form", checksum: "abc" };
    m.packageCheck.mockResolvedValue({ ok: true, model: "res.partner", view_type: "form", base_view_id: 1, fields_to_create: [{ name: "x_tier", ttype: "char", field_description: "Tier" }], problems: [], has_changes_here: true, steps: 3, from_major: 17, to_major: 18 });
    m.packageImport.mockResolvedValue({ ok: true, fields_created: ["x_tier"] });
    const onChanged = vi.fn();
    render(
      <BuilderSheet open onOpenChange={vi.fn()} tab="package" onTab={vi.fn()} connectionId="c1" model="res.partner" viewType="form" viewId={null}
        layerHash={null} onOpenScreen={vi.fn()} onChanged={onChanged} errorText={errorText} />,
    );
    const file = new File([JSON.stringify(pkg)], "p.json", { type: "application/json" });
    Object.defineProperty(file, "text", { value: async () => JSON.stringify(pkg) });
    fireEvent.change(screen.getByLabelText("Package file"), { target: { files: [file] } });
    const box = await screen.findByText(/from Odoo 17 to Odoo 18/);
    expect(screen.getByText(/Will create fields: Tier/)).toBeInTheDocument();
    expect(screen.getByText(/Importing replaces them/)).toBeInTheDocument();
    fireEvent.click(within(box.parentElement as HTMLElement).getByRole("button", { name: "Import" }));
    await waitFor(() => expect(m.packageImport).toHaveBeenCalledWith("c1", pkg, true));
    expect(onChanged).toHaveBeenCalled();
  });
});
