import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
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
  n("sheet:main", "sheet", [n("group:a", "group", [n("field:phone", "field", [], { label: "Phone" }), n("field:mobile", "field", [], { label: "Mobile" })])]),
], { kind: "root" });
const moved = n("root", "form", [
  n("sheet:main", "sheet", [n("group:a", "group", [n("field:mobile", "field", [], { label: "Mobile" }), n("field:phone", "field", [], { label: "Phone" })])]),
], { kind: "root" });

const compile = vi.fn(async () => ({ arch: "<data/>", steps: [{ op: "move", xpath: ["//field[@name='mobile']"] }], dropped: [], warnings: [], issues: [], blocking: false, expected_tree: moved }));
vi.mock("@/lib/api", () => ({
  api: {
    widgets: vi.fn(async () => ({ major: 19, widgets: [] })),
    defaultGet: vi.fn(async () => ({ value: null, set: false })),
    presence: vi.fn(async () => ({ others: [], ttl: 60 })),
    guardCheck: vi.fn(async () => ({ has_layer: false, ok: true, summary: "", steps: [] })),
    engineLoad: vi.fn(async () => ({
      major: 19,
      model: "res.partner",
      view_type: "form",
      base_view_id: 1,
      combined_arch: "<form/>",
      arch_hash: "x",
      tree,
      fields: { phone: { string: "Phone", type: "char" }, mobile: { string: "Mobile", type: "char" } },
      layer: null,
    })),
    engineRecords: vi.fn(async () => ({
      records: [{ id: 1, display_name: "A" }, { id: 2, display_name: "B" }, { id: 3, display_name: "C" }],
      total: 3,
      fields: ["phone"],
      picks: { longest: 2, emptiest: 3 },
    })),
    engineCompile: (...a: unknown[]) => compile(...(a as [])),
    enginePublish: vi.fn(),
    engineRevert: vi.fn(),
    roles: vi.fn(async () => ({ roles: [], admin_role: "base.group_system", based_on: "" })),
    commentsList: vi.fn(async () => ({ comments: [] })),
  },
}));
vi.mock("sonner", () => ({ toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), message: vi.fn() }) }));

import { ViewDesignerShell } from "./ViewDesignerShell";

afterEach(() => cleanup());

describe("ViewDesignerShell", () => {
  it("loads the screen, steps records, moves by keyboard and counts pending changes", async () => {
    render(<ViewDesignerShell connectionId="1" />);
    await waitFor(() => expect(screen.getByTestId("vd-record-pos")).toHaveTextContent("Record 1 of 3"));
    expect(screen.getByTestId("vd-version")).toHaveTextContent("Odoo 19");
    expect(screen.queryByTestId("vd-key-hints")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Longest" }));
    expect(screen.getByTestId("vd-record-pos")).toHaveTextContent("Record 2 of 3");

    const layers = screen.getByTestId("vd-layers");
    const mobile = within(layers).getAllByRole("treeitem").find((i) => i.getAttribute("data-row-id") === "field:mobile")!;
    fireEvent.click(mobile);
    expect(screen.getByTestId("vd-key-hints")).toBeInTheDocument();
    fireEvent.keyDown(mobile, { key: "ArrowUp", altKey: true });
    await waitFor(() => expect(screen.getByTestId("vd-publish")).toHaveTextContent("Publish changes (1)"));
    await waitFor(() => expect(compile).toHaveBeenCalled());
    expect(compile.mock.calls[0]).toEqual(["1", "res.partner", "form", [{ op: "move", node: "field:mobile", target: "field:phone", position: "before" }], null]);
  });
});
