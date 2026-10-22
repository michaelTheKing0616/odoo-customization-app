import { describe, expect, it } from "vitest";
import {
  PRIMARY_CTA,
  applyUnlockReason,
  configErrorGuide,
  configHonestyGuide,
  configStepFromState,
  emptyConfigGuide,
  idleConfigGuide,
  planHonestyLabel,
  primaryCtaForPanel,
  sanitizeConfigCopy,
} from "@/lib/configScreen";

describe("configScreen", () => {
  it("names Save the setting as the primary CTA", () => {
    expect(PRIMARY_CTA).toBe("Save the setting");
    expect(primaryCtaForPanel("settings-board")).toBe("Save the setting");
    expect(primaryCtaForPanel("day1")).toBe("Apply");
  });

  it("steps Recipes → Configure → Test run → Save from state", () => {
    expect(
      configStepFromState({
        panel: "home",
        recipeCount: 0,
        hasDryRun: false,
        hasWriteResult: false,
      }),
    ).toBe(1);
    expect(
      configStepFromState({
        panel: "day1",
        recipeCount: 4,
        hasDryRun: false,
        hasWriteResult: false,
      }),
    ).toBe(2);
    expect(
      configStepFromState({
        panel: "settings-board",
        recipeCount: 4,
        hasDryRun: true,
        hasWriteResult: false,
      }),
    ).toBe(3);
    expect(
      configStepFromState({
        panel: "settings-board",
        recipeCount: 4,
        hasDryRun: false,
        hasWriteResult: true,
      }),
    ).toBe(4);
  });

  it("empty, idle, honesty, and error guides are what/why/next without em dashes", () => {
    const empty = emptyConfigGuide();
    const idle = idleConfigGuide();
    const honesty = configHonestyGuide();
    const err = configErrorGuide("dry_run", "Connection timed out");
    for (const g of [empty, idle, honesty, err]) {
      expect(g.title.length).toBeGreaterThan(3);
      expect(g.why.length).toBeGreaterThan(5);
      expect(g.next.length).toBeGreaterThan(5);
      expect(`${g.title}${g.why}${g.next}`).not.toMatch(/[\u2014\u2013]/);
    }
    expect(err.why.toLowerCase()).toMatch(/took too long|timed/);
    expect(err.next.toLowerCase()).toContain("test run");
    expect(sanitizeConfigCopy("A — B – C")).toBe("A - B - C");
  });

  it("plan honesty labels distinguish test run from writes", () => {
    expect(planHonestyLabel(true)).toContain("no writes");
    expect(planHonestyLabel(false)).toContain("writes applied");
  });

  it("unlock reason explains test run gate", () => {
    expect(
      applyUnlockReason({ canApply: false, panel: "settings-board" }),
    ).toMatch(/Save the setting unlocks/i);
    expect(applyUnlockReason({ canApply: true, panel: "day1" })).toBeNull();
    expect(applyUnlockReason({ canApply: false, panel: "home" })).toBeNull();
  });
});
