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
