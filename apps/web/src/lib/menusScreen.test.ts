import { describe, expect, it } from "vitest";
import { menusHonestyGuide, menusSessionBadge, sanitizeMenusCopy } from "@/lib/menusScreen";

describe("menusScreen", () => {
  it("folds save honesty for the studio bar", () => {
    const g = menusHonestyGuide();
    expect(g.title.toLowerCase()).toMatch(/save/);
    expect(`${g.title}${g.why}${g.next}`).not.toMatch(/\u2014|\u2013/);
    expect(menusSessionBadge({ unsaved: true, empty: false }).variant).toBe("warning");
    expect(sanitizeMenusCopy("a — b")).toBe("a - b");
  });
});
