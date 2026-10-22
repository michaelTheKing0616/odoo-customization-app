import { describe, expect, it } from "vitest";
import {
  FEATURED_TOOL_ID,
  OPS_HUB_GROUPS,
  OPS_HUB_TOOLS,
  PAGE_DESCRIPTION,
  PAGE_TITLE,
  PRIMARY_CTA,
  featuredTool,
  opsHubHonestyGuide,
  opsHubHasEmDash,
  pickToolGuide,
  sanitizeOpsHubCopy,
  toolsForGroup,
} from "./operationsHubScreen";

describe("operationsHubScreen", () => {
  it("keeps hub copy free of em dashes and fake metrics tone", () => {
    const blobs = [
      PAGE_TITLE,
      PAGE_DESCRIPTION,
      PRIMARY_CTA,
      ...OPS_HUB_TOOLS.flatMap((t) => [t.label, t.description, t.hint]),
      ...OPS_HUB_GROUPS.flatMap((g) => [g.label, g.blurb]),
      ...Object.values(pickToolGuide()),
      ...Object.values(opsHubHonestyGuide()),
    ];
    for (const text of blobs) {
      expect(opsHubHasEmDash(text)).toBe(false);
      expect(sanitizeOpsHubCopy(text)).toBe(text);
    }
    expect(PAGE_DESCRIPTION.toLowerCase()).not.toMatch(/98\.7%|records today/);
  });

  it("features Bulk Suite as the sole primary CTA target", () => {
    expect(FEATURED_TOOL_ID).toBe("bulk-suite");
    expect(featuredTool().id).toBe("bulk-suite");
    expect(PRIMARY_CTA.toLowerCase()).toContain("bulk");
  });

  it("groups every tool exactly once", () => {
    const ids = OPS_HUB_TOOLS.map((t) => t.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids).toHaveLength(7);
    for (const group of OPS_HUB_GROUPS) {
      expect(toolsForGroup(group.id).length).toBeGreaterThan(0);
    }
    const grouped = OPS_HUB_GROUPS.flatMap((g) => toolsForGroup(g.id).map((t) => t.id));
    expect(grouped.sort()).toEqual([...ids].sort());
  });

  it("pick and honesty guides expose what / why / next", () => {
    const pick = pickToolGuide();
    const honesty = opsHubHonestyGuide();
    expect(pick.title.length).toBeGreaterThan(5);
    expect(pick.why.toLowerCase()).toContain("no invented");
    expect(pick.next.toLowerCase()).toContain("bulk");
    expect(honesty.why.toLowerCase()).toMatch(/write|change live/);
    expect(honesty.next.toLowerCase()).toContain("test run");
  });

  it("sanitizeOpsHubCopy replaces unicode dashes", () => {
    expect(sanitizeOpsHubCopy("A—B–C")).toBe("A-B-C");
  });
});
