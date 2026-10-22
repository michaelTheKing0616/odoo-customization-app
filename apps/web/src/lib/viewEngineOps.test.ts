import { describe, expect, it } from "vitest";
import type { EngineNode } from "@/lib/api/view-engine";
import {
  canDrop,
  describeOp,
  dropLabel,
  fieldCount,
  fieldsNotOnScreen,
  indexTree,
  keyboardMove,
  visibilityChips,
} from "./viewEngineOps";

const n = (id: string, tag: string, children: EngineNode[] = [], extra: Partial<EngineNode> = {}): EngineNode => ({
  id,
  tag,
  kind: tag === "field" ? "field" : "container",
  name: id.split(":")[1] ?? null,
  label: extra.label ?? id.split(":")[1] ?? tag,
  attrs: {},
  anchor: `//${tag}[@name='${id.split(":")[1]}']`,
  locked_reason: null,
  children,
  ...extra,
});

const tree = n("root", "form", [
  n("sheet:main", "sheet", [
    n("group:a", "group", [n("field:phone", "field", [], { label: "Phone" }), n("field:mobile", "field", [], { label: "Mobile" })]),
    n("group:b", "group", [n("field:email", "field", [], { label: "Email" })]),
    n("notebook:nb", "notebook", [n("page:other", "page", [n("field:ref", "field")], { label: "Other" })]),
    n("field:locked", "field", [], { anchor: null, locked_reason: "There are two of these." }),
  ]),
], { kind: "root" });
const index = indexTree(tree);

describe("viewEngineOps", () => {
  it("offers plain drop labels", () => {
    expect(dropLabel(index.byId.get("field:mobile"), "after", true)).toBe("Add after Mobile");
    expect(dropLabel(index.byId.get("group:b"), "inside", false)).toBe("Move into b");
  });

  it("refuses unsafe drops with plain reasons", () => {
    expect(canDrop(index, "field", "field:phone", "group:b", "inside").ok).toBe(true);
    expect(canDrop(index, "group", "group:a", "field:phone", "before")).toEqual({ ok: false, reason: "It can't go inside itself." });
    expect(canDrop(index, "field", "field:locked", "group:b", "inside").reason).toBe("There are two of these.");
    expect(canDrop(index, "page", "page:other", "group:b", "inside").reason).toBe("A tab can't go inside a group.");
    expect(canDrop(index, "field", null, "field:locked", "after").ok).toBe(false);
  });

  it("moves by keyboard without positional targets", () => {
    expect(keyboardMove(index, "field:mobile", "ArrowUp")).toEqual({ op: "move", node: "field:mobile", target: "field:phone", position: "before" });
    expect(keyboardMove(index, "field:phone", "ArrowDown")).toEqual({ op: "move", node: "field:phone", target: "field:mobile", position: "after" });
    expect(keyboardMove(index, "field:email", "ArrowLeft")).toEqual({ op: "move", node: "field:email", target: "group:b", position: "after" });
    expect(keyboardMove(index, "group:b", "ArrowRight")).toEqual({ op: "move", node: "group:b", target: "group:a", position: "inside" });
    expect(keyboardMove(index, "field:phone", "ArrowUp")).toBeNull();
    expect(keyboardMove(index, "field:locked", "ArrowUp")).toBeNull();
  });

  it("describes ops in plain words", () => {
    const label = (f: string) => (f === "vat" ? "Tax ID" : f);
    expect(describeOp({ op: "insert_field", field: "vat", target: "group:a", position: "inside" }, index, label)).toBe("Added Tax ID");
    expect(describeOp({ op: "hide", node: "field:email" }, index, label)).toBe("Hid Email");
    expect(describeOp({ op: "set_attr", node: "field:phone", attr: "string", value: "Work phone" }, index, label)).toBe("Renamed Phone to Work phone");
    expect(describeOp({ op: "wrap", nodes: ["field:phone", "field:mobile"], kind: "page", label: "X" }, index, label)).toBe("Put 2 items in a new tab");
  });

  it("counts fields per tab and lists fields not on screen", () => {
    expect(fieldCount(index.byId.get("page:other")!)).toBe(1);
    const rest = fieldsNotOnScreen(index, { phone: { string: "Phone" }, vat: { string: "Tax ID" }, image: { type: "binary" } }, "");
    expect(rest.map((f) => f.name)).toEqual(["vat"]);
    expect(fieldsNotOnScreen(index, { vat: { string: "Tax ID" } }, "zzz")).toEqual([]);
  });

  it("states visibility in plain words", () => {
    expect(visibilityChips(n("field:x", "field", [], { attrs: {} }))).toEqual(["Always shown", "Everyone who can open this"]);
    expect(visibilityChips(n("field:x", "field", [], { attrs: { invisible: "state == 'done'", groups: "base.group_system" } }))).toEqual([
      "Shown only sometimes",
      "Some roles only",
    ]);
  });
});
