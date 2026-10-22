import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("DesignerStudioRail extract hygiene", () => {
  it("owns tools-rail tabs including overlay and xpath (regression)", () => {
    const src = readFileSync(resolve(__dirname, "DesignerStudioRail.tsx"), "utf8");
    expect(src).toContain("FieldPalette");
    expect(src).toContain("OverlayEditor");
    expect(src).toContain("XPathInheritPanel");
    expect(src).toContain('id: "fields"');
    expect(src).toContain('id: "advanced"');
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
