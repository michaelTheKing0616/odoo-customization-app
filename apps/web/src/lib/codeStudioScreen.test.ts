import { describe, expect, it } from "vitest";
import { codeStudioHonestyGuide, codeStudioSessionBadge, sanitizeCodeStudioCopy } from "@/lib/codeStudioScreen";

describe("codeStudioScreen", () => {
  it("folds validate honesty for the studio bar", () => {
    const g = codeStudioHonestyGuide();
    expect(g.title.toLowerCase()).toMatch(/validate|option a/);
    expect(`${g.title}${g.why}${g.next}`).not.toMatch(/\u2014|\u2013/);
    expect(codeStudioSessionBadge("validated").variant).toBe("success");
    expect(sanitizeCodeStudioCopy("a — b")).toBe("a - b");
  });
});
