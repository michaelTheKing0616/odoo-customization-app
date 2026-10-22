import { describe, expect, it } from "vitest";
import {
  PRIMARY_CTA,
  blastRadiusFromState,
  bulkErrorGuide,
  bulkStepFromState,
  countIds,
  emptyBulkGuide,
  partialFailureGuide,
  runBlockedReason,
  sanitizeBulkCopy,
} from "@/lib/bulkSuiteScreen";

describe("bulkSuiteScreen", () => {
  it("names Run bulk action as the primary CTA", () => {
    expect(PRIMARY_CTA).toBe("Run bulk action");
  });

  it("steps Model → Select → Test run → Run from state", () => {
    expect(bulkStepFromState({ model: "", hasSelection: false, hasDryRun: false, hasWriteResult: false })).toBe(1);
    expect(bulkStepFromState({ model: "res.partner", hasSelection: false, hasDryRun: false, hasWriteResult: false })).toBe(2);
    expect(bulkStepFromState({ model: "res.partner", hasSelection: true, hasDryRun: false, hasWriteResult: false })).toBe(3);
    expect(bulkStepFromState({ model: "res.partner", hasSelection: true, hasDryRun: true, hasWriteResult: false })).toBe(3);
    expect(bulkStepFromState({ model: "res.partner", hasSelection: true, hasDryRun: false, hasWriteResult: true })).toBe(4);
  });

  it("counts explicit ids for blast radius", () => {
    expect(countIds("1, 2 3")).toBe(3);
    const blast = blastRadiusFromState({
      model: "res.partner",
      selectionMode: "ids",
      idsText: "10, 20, 30",
    });
    expect(blast.known).toBe(true);
    expect(blast.recordCount).toBe(3);
    expect(blast.label).toMatch(/3 records on 1 model/);
    expect(blast.label + blast.detail).not.toMatch(/[\u2014\u2013]/);
  });

  it("uses test run totals for blast radius when present", () => {
    const blast = blastRadiusFromState({
      model: "sale.order",
      selectionMode: "domain",
      idsText: "",
      resultTotal: 412,
      resultFailed: 0,
      dryRunResult: true,
      modelsTouched: 1,
    });
    expect(blast.label).toBe("412 records on 1 model");
    expect(blast.tone).toBe("accent");
    expect(blast.detail.toLowerCase()).toContain("test run");
  });

  it("asks for test run when domain blast radius is unknown", () => {
    const blast = blastRadiusFromState({
      model: "res.partner",
      selectionMode: "domain",
      idsText: "",
    });
    expect(blast.known).toBe(false);
    expect(blast.detail.toLowerCase()).toContain("test run");
  });

  it("blocks run for missing method or unsafe transition", () => {
    expect(
      runBlockedReason({
        busy: false,
        method: "",
        bulkSafe: null,
        selectionMode: "domain",
        idsText: "",
        domainText: "[]",
      }),
    ).toMatch(/discover/i);
    expect(
      runBlockedReason({
        busy: false,
        method: "action_confirm",
        bulkSafe: false,
        selectionMode: "domain",
        idsText: "",
        domainText: "[]",
      }),
    ).toMatch(/not bulk-safe/i);
  });

  it("empty and error guides are what/why/next without em dashes", () => {
    const empty = emptyBulkGuide();
    expect(empty.title.length).toBeGreaterThan(3);
    expect(empty.why.length).toBeGreaterThan(5);
    expect(empty.next.length).toBeGreaterThan(5);
    const err = bulkErrorGuide("dry_run", "Connection timed out");
    expect(err.why.toLowerCase()).toMatch(/took too long|timed/);
    expect(err.next.toLowerCase()).toContain("test run");
    expect(sanitizeBulkCopy("A — B – C")).toBe("A - B - C");
    expect(`${empty.title}${empty.why}${empty.next}${err.title}${err.why}${err.next}`).not.toMatch(
      /[\u2014\u2013]/,
    );
  });

  it("partial failure guide appears only when failed > 0", () => {
    expect(partialFailureGuide({ total: 10, succeeded: 10, failed: 0, model: "res.partner" })).toBeNull();
    const g = partialFailureGuide({ total: 10, succeeded: 6, failed: 4, model: "res.partner" });
    expect(g?.title).toMatch(/4 failure/);
    expect(g?.next.toLowerCase()).toContain("failed");
  });
});
