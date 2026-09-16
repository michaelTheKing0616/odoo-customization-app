import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("useDesignerPersist extract hygiene", () => {
  it("owns save/xpath/undo/rollback helpers", () => {
    const src = readFileSync(resolve(__dirname, "useDesignerPersist.ts"), "utf8");
    expect(src).toContain("export function useDesignerPersist");
    expect(src).toContain("async function onSave");
    expect(src).toContain("async function runXpathPreview");
    expect(src).toContain("function onSessionUndo");
  });

  it("page uses the hook instead of inline onSave", () => {
    const page = readFileSync(
      resolve(__dirname, "../../app/connections/[id]/designer/page.tsx"),
      "utf8",
    );
    expect(page).toContain("useDesignerPersist({");
    expect(page).not.toContain("async function onSave(");
  });
});
