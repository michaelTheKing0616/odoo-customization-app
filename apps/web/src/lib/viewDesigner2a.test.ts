import { describe, expect, it } from "vitest";
import type { EngineNode, EngineOp, ViewComment } from "@/lib/api/view-engine";
import {
  accessOps,
  conditionComplete,
  copyRuleOps,
  levelsFromGroups,
  markerSummary,
  nextSelection,
  openCounts,
  orphanThreads,
  ruleAttrsFor,
  threadsByNode,
  whyHidden,
} from "./viewDesigner2a";
import { indexTree } from "./viewEngineOps";

const node = (id: string, attrs: Record<string, string> = {}, extra: Partial<EngineNode> = {}): EngineNode => ({
  id, tag: "field", kind: "field", name: id.split(":")[1], label: id.split(":")[1], attrs, anchor: "//x", locked_reason: null, children: [], ...extra,
});

describe("viewDesigner2a helpers", () => {
  it("reads roles from groups and writes one set_access op per selected item", () => {
    expect(levelsFromGroups("sales_team.group_sale_manager,!base.group_portal")).toEqual({ "sales_team.group_sale_manager": "edit" });
    expect(accessOps(["field:a", "field:b"], { "g.x": "edit", "g.y": "see" })).toEqual([
      { op: "set_access", node: "field:a", edit: ["g.x"], see: ["g.y"] },
      { op: "set_access", node: "field:b", edit: ["g.x"], see: ["g.y"] },
    ]);
  });

  it("copies roles and rules, preferring pending rules made here", () => {
    const src = node("field:src", { groups: "g.m", invisible: "not is_company" });
    const pending: EngineOp[] = [
      { op: "set_condition", node: "field:src", attr: "required", sense: "show", condition: { match: "all", rules: [{ field: "x", op: "set" }] } },
    ];
    const out = copyRuleOps(src, ["field:t", "field:src"], pending);
    expect(out).toEqual([
      { op: "set_access", node: "field:t", edit: ["g.m"], see: [] },
      { op: "set_condition", node: "field:t", attr: "invisible", sense: "show", condition: null, copy_from: "field:src" },
      { op: "set_condition", node: "field:t", attr: "required", sense: "show", condition: { match: "all", rules: [{ field: "x", op: "set" }] } },
    ]);
  });

  it("multi-select adds and removes with shift/cmd, plain click selects one", () => {
    expect(nextSelection(["a"], "b", true)).toEqual(["a", "b"]);
    expect(nextSelection(["a", "b"], "a", true)).toEqual(["b"]);
    expect(nextSelection(["a", "b"], "c", false)).toEqual(["c"]);
  });

  it("explains why an item is hidden: role preview first, then Odoo's rule", () => {
    const n = node("field:a", { invisible: "x" }, { rules: { invisible: "Hidden when Stage is Won" } });
    expect(whyHidden(n, { "field:a": { visible: false, reason: "Only Sales / Administrator can see it." } })).toBe("Only Sales / Administrator can see it.");
    expect(whyHidden(n, null)).toBe("Hidden when Stage is Won");
    expect(whyHidden(node("field:b", { invisible: "1" }), null)).toBe("Always hidden on this screen.");
  });

  it("knows which rules an item can have and when a rule is complete", () => {
    expect(ruleAttrsFor(node("field:a"), "list")).toEqual(["invisible", "required", "readonly", "column_invisible"]);
    expect(ruleAttrsFor(node("group:g", {}, { tag: "group" }), "form")).toEqual(["invisible"]);
    expect(conditionComplete({ match: "all", rules: [{ field: "stage_id", op: "in", value: [] }] })).toBe(false);
    expect(conditionComplete({ match: "all", rules: [{ field: "active", op: "is_true" }] })).toBe(true);
  });

  it("summarises compare markers and groups comment threads", () => {
    expect(markerSummary({ a: "moved", b: "moved", c: "added" })).toBe("2 moved, 1 added");
    expect(markerSummary({})).toBe("No differences");
    const c = (id: string, node_id: string, parent_id: string | null = null, resolved = false): ViewComment => ({
      id, node_id, parent_id, author: "You", body: id, resolved, created_at: null, resolved_at: null,
    });
    const list = [c("1", "field:a"), c("2", "field:a", "1"), c("3", "field:a", null, true), c("4", "field:gone")];
    expect(threadsByNode(list).get("field:a")?.[0].replies.map((r) => r.id)).toEqual(["2"]);
    expect(openCounts(list)).toEqual({ "field:a": 1, "field:gone": 1 });
    const index = indexTree({ ...node("root"), tag: "form", kind: "root", children: [node("field:a")] });
    expect(orphanThreads(list, index).map((o) => o.id)).toEqual(["4"]);
  });
});
