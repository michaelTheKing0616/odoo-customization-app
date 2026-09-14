import { describe, expect, it } from "vitest";
import {
  DESIGNER_HISTORY_CAP,
  designerHistoryIsDirty,
  markDesignerHistoryPublished,
  pushDesignerHistory,
  redoDesignerHistory,
  resetDesignerHistory,
  undoDesignerHistory,
} from "./designerHistory";

type Snap = { n: number; label?: string };

describe("designerHistory", () => {
  it("push / undo / redo restores snapshots", () => {
    let state = resetDesignerHistory<Snap>({ n: 0 });
    expect(designerHistoryIsDirty(state)).toBe(false);

    state = pushDesignerHistory(state, { n: 1 }, { label: "Add field", now: 1 });
    state = pushDesignerHistory(state, { n: 2 }, { label: "Move field", now: 2 });
    expect(designerHistoryIsDirty(state)).toBe(true);
    expect(state.present).toEqual({ n: 2 });

    const undone = undoDesignerHistory(state);
    expect(undone).not.toBeNull();
    state = undone!.state;
    expect(undone!.snapshot).toEqual({ n: 1 });
    expect(state.present).toEqual({ n: 1 });

    const redone = redoDesignerHistory(state);
    expect(redone).not.toBeNull();
    state = redone!.state;
    expect(redone!.snapshot).toEqual({ n: 2 });
    expect(state.present).toEqual({ n: 2 });
  });

  it("coalesces rapid edits with the same key into one undo step", () => {
    let state = resetDesignerHistory<Snap>({ n: 0, label: "" });
    state = pushDesignerHistory(state, { n: 0, label: "A" }, {
      label: "Edit field properties",
      coalesceKey: "field:1",
      now: 1_000,
    });
    state = pushDesignerHistory(state, { n: 0, label: "Ab" }, {
      label: "Edit field properties",
      coalesceKey: "field:1",
      now: 1_200,
    });
    state = pushDesignerHistory(state, { n: 0, label: "Abc" }, {
      label: "Edit field properties",
      coalesceKey: "field:1",
      now: 1_400,
    });
    expect(state.past).toHaveLength(1);
    expect(state.present.label).toBe("Abc");

    const undone = undoDesignerHistory(state);
    expect(undone!.snapshot).toEqual({ n: 0, label: "" });
  });

  it("does not coalesce after the window or with a different key", () => {
    let state = resetDesignerHistory<Snap>({ n: 0 });
    state = pushDesignerHistory(state, { n: 1 }, {
      coalesceKey: "a",
      now: 1_000,
    });
    state = pushDesignerHistory(state, { n: 2 }, {
      coalesceKey: "a",
      now: 2_000,
    });
    expect(state.past).toHaveLength(2);

    state = pushDesignerHistory(state, { n: 3 }, {
      coalesceKey: "b",
      now: 2_100,
    });
    expect(state.past).toHaveLength(3);
  });

  it("caps the past stack", () => {
    let state = resetDesignerHistory<Snap>({ n: 0 });
    for (let i = 1; i <= DESIGNER_HISTORY_CAP + 5; i += 1) {
      state = pushDesignerHistory(state, { n: i }, { now: i });
    }
    expect(state.past).toHaveLength(DESIGNER_HISTORY_CAP);
    expect(state.past[0]?.snapshot).toEqual({ n: 5 });
    expect(state.present).toEqual({ n: DESIGNER_HISTORY_CAP + 5 });
  });

  it("undo at the baseline is a no-op; publish clears session undo", () => {
    let state = resetDesignerHistory<Snap>({ n: 0 });
    expect(undoDesignerHistory(state)).toBeNull();
    expect(redoDesignerHistory(state)).toBeNull();

    state = pushDesignerHistory(state, { n: 1 }, { now: 1 });
    state = markDesignerHistoryPublished(state);
    expect(designerHistoryIsDirty(state)).toBe(false);
    expect(state.past).toHaveLength(0);
    expect(undoDesignerHistory(state)).toBeNull();
  });

  it("ignores a push that equals the present snapshot", () => {
    const state = resetDesignerHistory<Snap>({ n: 1 });
    const same = pushDesignerHistory(state, { n: 1 }, { now: 1 });
    expect(same).toBe(state);
  });
});
