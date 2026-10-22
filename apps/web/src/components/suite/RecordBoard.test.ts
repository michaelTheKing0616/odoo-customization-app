import { describe, expect, it } from "vitest";
import { groupForBoard, pickBoardField } from "./RecordBoard";
import type { RecField } from "@/lib/api/suite";

const f = (name: string, type: string, choices: { value: string; label: string }[] = []): RecField =>
  ({ name, label: name, type, relation: null, required: false, stored: true, editable: true, why_not: null, sortable: true, groupable: true, choices });

describe("RecordBoard (touch 80)", () => {
  it("prefers stage, then state, else no board", () => {
    expect(pickBoardField([f("state", "selection"), f("stage_id", "many2one")])?.name).toBe("stage_id");
    expect(pickBoardField([f("name", "char")])).toBeNull();
  });
  it("keeps empty selection columns and groups many2one pairs", () => {
    const st = f("state", "selection", [{ value: "draft", label: "Draft" }, { value: "done", label: "Done" }]);
    const g = groupForBoard([{ id: 1, display_name: "A", state: "done" }], st);
    expect(g.map((c) => [c.label, c.rows.length])).toEqual([["Draft", 0], ["Done", 1]]);
    const sg = groupForBoard([{ id: 2, display_name: "B", stage_id: [5, "New"] }], f("stage_id", "many2one"));
    expect(sg[0].label).toBe("New");
  });
});
