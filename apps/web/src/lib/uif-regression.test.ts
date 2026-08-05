import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

describe("duplicate section bugs (UIF-1)", () => {
  it("bulk-suite renders each section heading once", () => {
    const file = path.join(
      process.cwd(),
      "src/app/connections/[id]/bulk-suite/page.tsx",
    );
    const src = fs.readFileSync(file, "utf8");
    const headings = [
      "Mass field edit",
      "Duplicate detection & merge",
      "Bulk activities",
      "Bulk security",
      "Bulk portal access",
      "Bulk send message",
    ];
    for (const h of headings) {
      const count = (src.match(new RegExp(`<h2[^>]*>${h}</h2>`, "g")) ?? []).length;
      expect(count, h).toBe(1);
    }
  });

  it("housekeeping renders stored compute recompute once", () => {
    const file = path.join(
      process.cwd(),
      "src/app/connections/[id]/housekeeping/page.tsx",
    );
    const src = fs.readFileSync(file, "utf8");
    const count = (src.match(/Stored compute recompute/g) ?? []).length;
    expect(count).toBe(1);
  });
});
