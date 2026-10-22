import { describe, expect, it } from "vitest";
import type { EngineNode } from "@/lib/api/view-engine";
import type { Finding, Placement } from "@/lib/api/view-engine-2b";
import { addBlock, allFixOps, blockCount, errorDetail, healthWord, isPublishConflict, moveBlock, newBlock, placeElement, placeField, updateBlock } from "./viewDesigner2b";

const n = (id: string, tag: string, children: EngineNode[] = [], extra: Partial<EngineNode> = {}): EngineNode => ({
  id, tag, kind: tag === "field" ? "field" : "container", name: id.split(":")[1] ?? null, label: id, attrs: {},
  anchor: `//${tag}`, locked_reason: null, children, ...extra,
});
const form = (extra: EngineNode[] = []) =>
  n("root", "form", [...extra, n("sheet:s", "sheet", [n("group:a", "group", [n("field:name", "field")]), n("notebook:nb", "notebook", [n("page:p", "page")])])], { kind: "root" });

describe("viewDesigner2b helpers", () => {
  it("reads API error detail and spots publish conflicts only on 409", () => {
    const e = Object.assign(new Error("x"), { status: 409, detail: { conflict: true } });
    expect(errorDetail(e)).toEqual({ conflict: true });
    expect(isPublishConflict(e)).toBe(true);
    expect(isPublishConflict(Object.assign(new Error("x"), { status: 400, detail: { conflict: true } }))).toBe(false);
    expect(errorDetail("nope")).toBeNull();
  });

  it("words the health score", () => {
    expect(healthWord(90).word).toBe("Good");
    expect(healthWord(70).tone).toBe("fair");
    expect(healthWord(10).word).toBe("Needs work");
  });

  it("collects every fix once, in order", () => {
    const a = { op: "set_attr", node: "x", attr: "string", value: "A" } as const;
    const b = { op: "remove", node: "y" } as unknown as Finding["ops"][number];
    const f: Finding[] = [{ kind: "k", text: "", ops: [a] }, { kind: "k", text: "", ops: [a, b] }, { kind: "k", text: "", ops: [] }];
    expect(allFixOps(f)).toEqual([a, b]);
  });

  it("places library elements where Odoo expects them, and refuses duplicates", () => {
    expect(placeElement("header", form(), null)).toEqual({ target: "sheet:s", position: "before" });
    expect(placeElement("header", form([n("header:h", "header")]), null)).toHaveProperty("error");
    expect(placeElement("statusbar", form(), null)).toHaveProperty("error");
    expect(placeElement("statusbar", form([n("header:h", "header")]), null)).toEqual({ target: "header:h", position: "inside" });
    expect(placeElement("chatter", form(), null)).toEqual({ target: "sheet:s", position: "after" });
    expect(placeElement("smart_button", form(), null)).toHaveProperty("error");
    expect(placeElement("page", form(), null)).toEqual({ target: "notebook:nb", position: "inside" });
    expect(placeElement("button_box", form(), null)).toEqual({ target: "group:a", position: "before" });
  });

  it("puts a new field in the selected group, after a selected field, or at the end of a list", () => {
    const t = form();
    expect(placeField(t, null)).toEqual({ target: "group:a", position: "inside" });
    expect(placeField(t, n("field:name", "field"))).toEqual({ target: "field:name", position: "after" });
    expect(placeField(n("root", "list", [], { kind: "root" }), null)).toEqual({ target: "root", position: "inside" });
  });

  it("edits report block placements", () => {
    let p: Placement[] = [];
    p = addBlock(p, "top", newBlock("heading"));
    p = addBlock(p, "top", newBlock("qr", "name"));
    p = addBlock(p, "bottom", newBlock("watermark"));
    expect(blockCount(p)).toBe(3);
    p = moveBlock(p, "top", 0, 1);
    expect(p[0].blocks.map((b) => b.type)).toEqual(["qr", "heading"]);
    expect(moveBlock(p, "top", 0, -1)).toEqual(p);
    p = updateBlock(p, "bottom", 0, null);
    expect(p.map((x) => x.slot)).toEqual(["top"]);
    p = updateBlock(p, "top", 1, { type: "heading", text: "Hi" });
    expect(p[0].blocks[1]).toEqual({ type: "heading", text: "Hi" });
  });
});
