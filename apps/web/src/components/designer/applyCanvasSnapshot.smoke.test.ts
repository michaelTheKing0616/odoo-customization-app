import { describe, expect, it } from "vitest";
import { applyCanvasSnapshot } from "./applyCanvasSnapshot";

describe("applyCanvasSnapshot", () => {
  it("exports a function", () => {
    expect(typeof applyCanvasSnapshot).toBe("function");
  });
});
