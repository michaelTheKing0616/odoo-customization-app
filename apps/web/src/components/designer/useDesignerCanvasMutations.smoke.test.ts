import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("useDesignerCanvasMutations extract hygiene", () => {
  it("exports layout + bind mutators", () => {
    const src = readFileSync(resolve(__dirname, "useDesignerCanvasMutations.ts"), "utf8");
    expect(src).toContain("export function useDesignerCanvasMutations");
    expect(src).toContain("function addFieldToGroup");
    expect(src).toContain("function submitBindDialog");
    expect(src).toContain("function reorderFormNode");
  });

  it("page uses the hook instead of inline addGroup", () => {
    const page = readFileSync(
      resolve(__dirname, "../../app/connections/[id]/designer/page.tsx"),
      "utf8",
    );
    expect(page).toContain("useDesignerCanvasMutations({");
    expect(page).not.toContain("function addGroup()");
  });
});
