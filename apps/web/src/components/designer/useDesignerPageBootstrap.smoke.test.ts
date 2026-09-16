import { describe, expect, it } from "vitest";
import { useDesignerPageBootstrap } from "./useDesignerPageBootstrap";

describe("useDesignerPageBootstrap", () => {
  it("exports a hook function", () => {
    expect(typeof useDesignerPageBootstrap).toBe("function");
  });
});
