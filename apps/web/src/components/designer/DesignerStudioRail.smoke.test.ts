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

  it("page delegates rail to DesignerStudioRail", () => {
    const page = readFileSync(
      resolve(__dirname, "../../app/connections/[id]/designer/page.tsx"),
      "utf8",
    );
    expect(page).toContain("<DesignerStudioRail");
    expect(page).not.toMatch(/rail=\{\s*\n\s*<DesignerToolsRail/);
  });
});
