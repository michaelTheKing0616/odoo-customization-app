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

  it("classic page retired: redirects to the current designer, which mounts ViewDesignerShell", () => {
    const classic = readFileSync(
      resolve(__dirname, "../../app/connections/[id]/designer/classic/page.tsx"),
      "utf8",
    );
    expect(classic).toContain("redirect(");
    expect(classic).toContain("/designer");
    const current = readFileSync(
      resolve(__dirname, "../../app/connections/[id]/view-designer/page.tsx"),
      "utf8",
    );
    expect(current).toContain("<ViewDesignerShell");
  });
});
