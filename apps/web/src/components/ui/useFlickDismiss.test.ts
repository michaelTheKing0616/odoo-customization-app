import { describe, expect, it } from "vitest";
import { flickOffset, shouldDismiss } from "./useFlickDismiss";

describe("flick to dismiss", () => {
  it("follows the finger toward the edge and resists the other way", () => {
    expect(flickOffset(50, 1)).toBe(50);
    expect(Math.abs(flickOffset(-100, 1))).toBe(20);
  });
  it("dismisses on distance or a quick fling", () => {
    expect(shouldDismiss(200, 1, 400, 0)).toBe(true);
    expect(shouldDismiss(30, 1, 400, 0.8)).toBe(true);
    expect(shouldDismiss(30, 1, 400, 0.1)).toBe(false);
    expect(shouldDismiss(-200, 1, 400, -1)).toBe(false);
  });
});
