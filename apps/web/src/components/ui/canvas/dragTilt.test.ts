import { describe, expect, it } from "vitest";
import { dragTilt } from "./ReorderableBlocks";

describe("dragTilt", () => {
  it("never tilts past 3 degrees", () => {
    let t = 0;
    for (let i = 0; i < 50; i++) t = dragTilt(10, t);
    expect(t).toBeLessThanOrEqual(3);
    expect(dragTilt(-10, -3)).toBeGreaterThanOrEqual(-3);
  });
});
