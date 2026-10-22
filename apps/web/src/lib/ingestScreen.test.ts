import { describe, expect, it } from "vitest";
import {
  PRIMARY_CTA,
  emptyIngestGuide,
  ingestHonestyGuide,
  ingestSessionBadge,
  sanitizeIngestCopy,
} from "@/lib/ingestScreen";

describe("ingestScreen", () => {
  it("names Commit as the primary CTA", () => {
    expect(PRIMARY_CTA).toBe("Commit");
  });

  it("folds test run honesty for the studio bar", () => {
    const g = ingestHonestyGuide();
    expect(g.title.toLowerCase()).toMatch(/[Tt]est run/);
    expect(`${g.title}${g.why}${g.next}`).not.toMatch(/\u2014|\u2013/);
    expect(ingestSessionBadge("upload").label).toBe("Upload");
    expect(ingestSessionBadge("commit").variant).toBe("success");
  });

  it("empty guide has what / why / next without em dashes", () => {
    const g = emptyIngestGuide();
    expect(g.title.length).toBeGreaterThan(3);
    expect(`${g.title}${g.why}${g.next}`).not.toMatch(/\u2014|\u2013/);
  });

  it("sanitizes em dashes", () => {
    expect(sanitizeIngestCopy("a — b")).toBe("a - b");
  });
});
