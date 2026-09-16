import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

describe("DesignerAdvancedStructureCanvas extract hygiene", () => {
  it("imports uid used by search filter adders (regression)", () => {
    const src = readFileSync(
      resolve(__dirname, "DesignerAdvancedStructureCanvas.tsx"),
      "utf8",
    );
    expect(src).toMatch(/import \{[^}]*\buid\b[^}]*\} from "@\/components\/designer\/designer-model"/);
    expect(src).toContain('uid("sf")');
    expect(src).toContain('uid("sg")');
  });
});
