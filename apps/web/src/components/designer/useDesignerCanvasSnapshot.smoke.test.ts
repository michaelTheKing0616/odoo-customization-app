import { describe, expect, it } from "vitest";
import { useDesignerCanvasSnapshot } from "./useDesignerCanvasSnapshot";

describe("useDesignerCanvasSnapshot", () => {
  it("exports a hook function", () => {
    expect(typeof useDesignerCanvasSnapshot).toBe("function");
  });
});
