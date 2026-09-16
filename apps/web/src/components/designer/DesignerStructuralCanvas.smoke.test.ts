import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("DesignerStructuralCanvas extract hygiene", () => {
  it("owns form/list/kanban structural layouts", () => {
    const src = readFileSync(resolve(__dirname, "DesignerStructuralCanvas.tsx"), "utf8");
    expect(src).toContain("FormCanvas");
    expect(src).toContain("OdooListView");
    expect(src).toContain("KanbanCardPreview");
    expect(src).toContain('data-testid="designer-form-layout"');
  });

  it("page delegates structural canvas to DesignerStructuralCanvas", () => {
    const page = readFileSync(
      resolve(__dirname, "../../app/connections/[id]/designer/page.tsx"),
      "utf8",
    );
    expect(page).toContain("<DesignerStructuralCanvas");
    expect(page).not.toContain("const formStructuralCanvas");
  });
});
