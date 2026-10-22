import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("useDesignerViewSpecs extract hygiene", () => {
  it("builds all view-type specs including activeViewSpec", () => {
    const src = readFileSync(resolve(__dirname, "useDesignerViewSpecs.ts"), "utf8");
    expect(src).toContain("const formSpec = useMemo");
    expect(src).toContain("const activeViewSpec = useMemo");
    expect(src).toContain("export function useDesignerViewSpecs");
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
