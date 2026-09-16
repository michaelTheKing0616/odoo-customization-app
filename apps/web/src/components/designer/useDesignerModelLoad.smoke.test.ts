import { describe, expect, it } from "vitest";
import { useDesignerModelLoad } from "./useDesignerModelLoad";

describe("useDesignerModelLoad", () => {
  it("exports a hook function", () => {
    expect(typeof useDesignerModelLoad).toBe("function");
  });
});
