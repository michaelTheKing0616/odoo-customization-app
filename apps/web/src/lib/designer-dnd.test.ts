import { describe, expect, it } from "vitest";
import {
  insertAt,
  insertIndexFromClientY,
  moveItem,
  readCanvasFieldId,
  readPaletteFieldName,
  setCanvasFieldDragData,
  setPaletteDragData,
} from "./designer-dnd";

function mockTransfer(initial: Record<string, string> = {}) {
  const store: Record<string, string> = { ...initial };
  const dt = {
    types: Object.keys(store) as string[],
    effectAllowed: "none" as string,
    setData(type: string, value: string) {
      store[type] = value;
      if (!dt.types.includes(type)) dt.types.push(type);
    },
    getData(type: string) {
      return store[type] ?? "";
    },
  };
  return dt as unknown as DataTransfer;
}

describe("designer-dnd", () => {
  it("writes and reads palette field names", () => {
    const dt = mockTransfer();
    setPaletteDragData(dt, "x_partner_id");
    expect(readPaletteFieldName(dt)).toBe("x_partner_id");
  });

  it("distinguishes canvas reorder payload from palette", () => {
    const dt = mockTransfer();
    setCanvasFieldDragData(dt, "f1", "x_name");
    expect(readCanvasFieldId(dt)).toBe("f1");
    expect(readPaletteFieldName(dt)).toBe("x_name");
  });

  it("computes insert index from midpoints", () => {
    const rects = [
      { top: 0, height: 40 },
      { top: 40, height: 40 },
      { top: 80, height: 40 },
    ];
    expect(insertIndexFromClientY(10, rects)).toBe(0);
    expect(insertIndexFromClientY(45, rects)).toBe(1);
    expect(insertIndexFromClientY(200, rects)).toBe(3);
  });

  it("inserts and moves list items without mutating the source", () => {
    const src = ["a", "b", "c"];
    expect(insertAt(src, 1, "x")).toEqual(["a", "x", "b", "c"]);
    expect(src).toEqual(["a", "b", "c"]);
    expect(moveItem(src, 0, 2)).toEqual(["b", "a", "c"]);
    expect(moveItem(src, 2, 0)).toEqual(["c", "a", "b"]);
  });
});
