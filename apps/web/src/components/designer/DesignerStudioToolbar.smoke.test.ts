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

  it("page delegates toolbar to DesignerStudioToolbar", () => {
    const page = readFileSync(
      resolve(__dirname, "../../app/connections/[id]/designer/page.tsx"),
      "utf8",
    );
    expect(page).toContain("<DesignerStudioToolbar");
    expect(page).not.toContain('data-testid="designer-studio-toolbar"');
  });
});
