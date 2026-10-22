import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("DesignerStudioToolbar extract hygiene", () => {
  it("owns designer-studio-toolbar card", () => {
    const src = readFileSync(resolve(__dirname, "DesignerStudioToolbar.tsx"), "utf8");
    expect(src).toContain('data-testid="designer-studio-toolbar"');
    expect(src).toContain("Save to Odoo");
    expect(src).toContain("gridViewAllowed");
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
