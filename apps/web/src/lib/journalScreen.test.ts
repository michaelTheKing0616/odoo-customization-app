import { describe, expect, it } from "vitest";
import {
  PRIMARY_CTA,
  canRollback,
  emptyJournalGuide,
  idleJournalGuide,
  journalErrorGuide,
  journalHonestyGuide,
  journalStepFromState,
  partialRollbackGuide,
  reversibilityCopy,
  sanitizeJournalCopy,
} from "@/lib/journalScreen";

describe("journalScreen", () => {
  it("names Roll back as the primary CTA", () => {
    expect(PRIMARY_CTA).toBe("Roll back");
  });

  it("steps Timeline → Inspect → Roll back from state", () => {
    expect(
      journalStepFromState({
        entryCount: 0,
        hasSelection: false,
        rollbackDone: false,
        tab: "timeline",
      }),
    ).toBe(1);
    expect(
      journalStepFromState({
        entryCount: 3,
        hasSelection: true,
        rollbackDone: false,
        tab: "timeline",
      }),
    ).toBe(2);
    expect(
      journalStepFromState({
        entryCount: 3,
        hasSelection: true,
        rollbackDone: true,
        tab: "timeline",
      }),
    ).toBe(3);
    expect(
      journalStepFromState({
        entryCount: 3,
        hasSelection: true,
        rollbackDone: false,
        tab: "batch",
      }),
    ).toBe(1);
  });

  it("allows rollback for yes and partial only", () => {
    expect(canRollback("yes")).toBe(true);
    expect(canRollback("partial")).toBe(true);
    expect(canRollback("none")).toBe(false);
    expect(canRollback("no")).toBe(false);
  });

  it("empty, idle, honesty, partial, and error guides are what/why/next without em dashes", () => {
    const guides = [
      emptyJournalGuide(),
      idleJournalGuide(),
      journalHonestyGuide(),
      partialRollbackGuide(),
      journalErrorGuide("rollback", "Connection timed out"),
    ];
    for (const g of guides) {
      expect(g.title.length).toBeGreaterThan(3);
      expect(g.why.length).toBeGreaterThan(5);
      expect(g.next.length).toBeGreaterThan(5);
      expect(`${g.title}${g.why}${g.next}`).not.toMatch(/[\u2014\u2013]/);
    }
    expect(journalErrorGuide("rollback", "Connection timed out").why.toLowerCase()).toMatch(
      /took too long|timed/,
    );
    expect(sanitizeJournalCopy("A — B – C")).toBe("A - B - C");
    expect(reversibilityCopy("partial")).toMatch(/Dropped columns cannot be restored/);
    expect(reversibilityCopy("partial")).not.toMatch(/[\u2014\u2013]/);
  });
});
