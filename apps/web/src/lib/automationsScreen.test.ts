import { describe, expect, it } from "vitest";
import { automationsHonestyGuide, sanitizeAutomationsCopy } from "@/lib/automationsScreen";

describe("automationsScreen", () => {
  it("folds Option A honesty for the studio bar", () => {
    const g = automationsHonestyGuide();
    expect(g.title.toLowerCase()).toMatch(/option a|python/);
    expect(`${g.title}${g.why}${g.next}`).not.toMatch(/\u2014|\u2013/);
    expect(sanitizeAutomationsCopy("a — b")).toBe("a - b");
  });
});
