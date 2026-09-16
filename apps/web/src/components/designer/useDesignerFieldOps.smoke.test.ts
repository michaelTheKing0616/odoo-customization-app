import { describe, expect, it } from "vitest";
import { useDesignerFieldOps } from "./useDesignerFieldOps";

describe("useDesignerFieldOps", () => {
  it("exports a hook function", () => {
    expect(typeof useDesignerFieldOps).toBe("function");
  });
});
