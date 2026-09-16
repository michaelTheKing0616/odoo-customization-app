import { describe, expect, it } from "vitest";
import { useDesignerFieldInspector } from "./useDesignerFieldInspector";

describe("useDesignerFieldInspector", () => {
  it("exports a hook function", () => {
    expect(typeof useDesignerFieldInspector).toBe("function");
  });
});
