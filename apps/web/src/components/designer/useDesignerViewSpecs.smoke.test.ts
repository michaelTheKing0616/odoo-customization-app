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

  it("page uses the hook instead of inline formSpec", () => {
    const page = readFileSync(
      resolve(__dirname, "../../app/connections/[id]/designer/page.tsx"),
      "utf8",
    );
    expect(page).toContain("useDesignerViewSpecs({");
    expect(page).not.toContain("const formSpec = useMemo");
  });
});
