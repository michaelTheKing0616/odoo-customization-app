import { existsSync, readFileSync } from "node:fs";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { EngineNode } from "@/lib/api/view-engine";
import { indexTree } from "@/lib/viewEngineOps";
import { EngineCanvas } from "./EngineCanvas";
import { LayersTree } from "./LayersTree";

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
    n("group:a", "group", [n("field:phone", "field", [], { label: "Phone" }), n("field:mobile", "field", [], { label: "Mobile" })]),
    n("widget:x", "widget", [], { kind: "block", label: "Odoo element: widget" }),
  ]),
], { kind: "root" });

const noop = () => {};

afterEach(() => cleanup());

describe("EngineCanvas", () => {
  it("renders fields and keeps unknown Odoo elements as blocks", () => {
    const index = indexTree(tree);
    render(<EngineCanvas tree={tree} index={index} record={null} selectedId={null} onSelect={noop} onMove={noop} onInsertField={noop} />);
    expect(screen.getByTestId("vd-field-phone")).toBeInTheDocument();
    expect(screen.getByTestId("vd-block")).toHaveTextContent("widget");
  });

  it("shows the chip bar only for the selected item", () => {
    const index = indexTree(tree);
    const onSelect = vi.fn();
    const { rerender } = render(
      <EngineCanvas tree={tree} index={index} record={null} selectedId={null} onSelect={onSelect} onMove={noop} onInsertField={noop} />,
    );
    expect(screen.queryByTestId("vd-chip-bar")).toBeNull();
    rerender(<EngineCanvas tree={tree} index={index} record={null} selectedId="field:phone" onSelect={onSelect} onMove={noop} onInsertField={noop} />);
    expect(screen.getByTestId("vd-chip-bar")).toHaveTextContent("Always shown");
  });
});

describe("LayersTree", () => {
  it("is a keyboard tree and moves with Alt+arrows", () => {
    const index = indexTree(tree);
    const onOp = vi.fn();
    const onRefused = vi.fn();
    const onSelect = vi.fn();
    render(<LayersTree tree={tree} index={index} selectedId="field:mobile" onSelect={onSelect} onOp={onOp} onRefused={onRefused} />);
    const t = screen.getByRole("tree");
    const items = within(t).getAllByRole("treeitem");
    expect(items).toHaveLength(6);
    const mobile = items.find((i) => i.getAttribute("data-row-id") === "field:mobile")!;
    expect(mobile).toHaveAttribute("tabindex", "0");
    fireEvent.keyDown(mobile, { key: "ArrowUp", altKey: true });
    expect(onOp).toHaveBeenCalledWith({ op: "move", node: "field:mobile", target: "field:phone", position: "before" });
    const phone = items.find((i) => i.getAttribute("data-row-id") === "field:phone")!;
    fireEvent.keyDown(phone, { key: "ArrowUp", altKey: true });
    expect(onRefused).toHaveBeenCalledWith("Phone can't move that way.");
    fireEvent.keyDown(mobile, { key: "Home" });
    expect(onSelect).toHaveBeenCalledWith("root");
  });
});

// Live trees captured from the disposable Odoo 17-20 databases (stage 1 acceptance).
const liveFiles = [17, 18, 19, 20].map((v) => `/tmp/vd1_trees_v${v}.json`).filter((f) => existsSync(f));

describe.skipIf(liveFiles.length === 0)("live Odoo screens", () => {
  it("renders every captured screen and lists every node in the layers tree", () => {
    for (const file of liveFiles) {
      const trees = JSON.parse(readFileSync(file, "utf8")) as Record<string, EngineNode>;
      for (const [key, live] of Object.entries(trees)) {
        const index = indexTree(live);
        const canvas = render(
          <EngineCanvas tree={live} index={index} record={null} selectedId={null} onSelect={noop} onMove={noop} onInsertField={noop} />,
        );
        expect(within(canvas.container).getByTestId("vd-canvas"), `${file} ${key}`).toBeInTheDocument();
        expect(canvas.container.querySelectorAll("[data-node-id]").length, `${file} ${key}`).toBeGreaterThan(3);
        canvas.unmount();
        const layers = render(<LayersTree tree={live} index={index} selectedId={null} onSelect={noop} onOp={noop} onRefused={noop} />);
        expect(within(layers.container).getAllByRole("treeitem").length, `${file} ${key}`).toBe(index.byId.size);
        layers.unmount();
      }
    }
  });
});
