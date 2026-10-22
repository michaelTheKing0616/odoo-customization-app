import { describe, expect, it } from "vitest";
import {
  PRIMARY_CTA,
  emptyPowerOpsGuide,
  idlePowerOpsGuide,
  isDangerRecipe,
  partialFailureGuide,
  powerOpsErrorGuide,
  powerOpsHonestyGuide,
  powerOpsStepFromState,
  runUnlockReason,
  sanitizePowerOpsCopy,
} from "@/lib/powerOpsScreen";

describe("powerOpsScreen", () => {
  it("names Run recipe as the primary CTA", () => {
    expect(PRIMARY_CTA).toBe("Run recipe");
  });

  it("steps Recipe → Configure → Test run → Run from state", () => {
    expect(
      powerOpsStepFromState({
        recipeCount: 0,
        hasRecipe: false,
        hasDryRun: false,
        hasWriteResult: false,
      }),
    ).toBe(1);
    expect(
      powerOpsStepFromState({
        recipeCount: 3,
        hasRecipe: true,
        hasDryRun: false,
        hasWriteResult: false,
      }),
    ).toBe(2);
    expect(
      powerOpsStepFromState({
        recipeCount: 3,
        hasRecipe: true,
        hasDryRun: true,
        hasWriteResult: false,
      }),
    ).toBe(3);
    expect(
      powerOpsStepFromState({
        recipeCount: 3,
        hasRecipe: true,
        hasDryRun: false,
        hasWriteResult: true,
      }),
    ).toBe(4);
  });

  it("marks destructive recipes from flag, tags, or id", () => {
    expect(isDangerRecipe({ id: "mass_archive", destructive: true })).toBe(true);
    expect(isDangerRecipe({ id: "safe_thing", destructive: false, tags: ["destructive"] })).toBe(
      true,
    );
    expect(isDangerRecipe({ id: "purge_journal_entries", destructive: false })).toBe(true);
    expect(isDangerRecipe({ id: "post_account_moves", destructive: false, tags: ["accounting"] })).toBe(
      false,
    );
  });

  it("empty, idle, honesty, and error guides are what/why/next without em dashes", () => {
    const empty = emptyPowerOpsGuide();
    const idle = idlePowerOpsGuide();
    const honesty = powerOpsHonestyGuide();
    const err = powerOpsErrorGuide("dry_run", "Connection timed out");
    for (const g of [empty, idle, honesty, err]) {
      expect(g.title.length).toBeGreaterThan(3);
      expect(g.why.length).toBeGreaterThan(5);
      expect(g.next.length).toBeGreaterThan(5);
      expect(`${g.title}${g.why}${g.next}`).not.toMatch(/[\u2014\u2013]/);
    }
    expect(err.why.toLowerCase()).toMatch(/took too long|timed/);
    expect(err.next.toLowerCase()).toContain("test run");
    expect(sanitizePowerOpsCopy("A — B – C")).toBe("A - B - C");
  });

  it("partial failure guide appears only when failed > 0", () => {
    expect(
      partialFailureGuide({ processed: 10, succeeded: 10, failed: 0, dryRun: false }),
    ).toBeNull();
    const live = partialFailureGuide({
      processed: 10,
      succeeded: 6,
      failed: 4,
      dryRun: false,
    });
    expect(live?.title).toMatch(/4 failure/);
    expect(live?.why.toLowerCase()).toContain("not rolled back");
    const dry = partialFailureGuide({
      processed: 10,
      succeeded: 6,
      failed: 4,
      dryRun: true,
    });
    expect(dry?.title.toLowerCase()).toContain("test run");
    expect(dry?.why.toLowerCase()).toContain("nothing was written");
  });

  it("explains why Run recipe stays locked", () => {
    expect(runUnlockReason({ selectedBlocked: true, canExecute: false })).toMatch(/blocked/i);
    expect(runUnlockReason({ selectedBlocked: false, canExecute: false })?.toLowerCase()).toContain(
      "test run",
    );
    expect(runUnlockReason({ selectedBlocked: false, canExecute: true })).toBeNull();
  });
});
