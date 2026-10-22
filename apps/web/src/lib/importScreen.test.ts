import { describe, expect, it } from "vitest";
import {
  PRIMARY_CTA,
  commitBlockedReason,
  countStripFromResult,
  emptyImportGuide,
  importErrorGuide,
  importHonestyGuide,
  importSessionBadge,
  importSessionHint,
  importStepFromState,
  mappingReady,
  partialFailureGuide,
  sanitizeImportCopy,
  unmappedColumns,
} from "@/lib/importScreen";
import type { DataImportCommitOut } from "@/lib/api";

const baseResult = (over: Partial<DataImportCommitOut> = {}): DataImportCommitOut => ({
  ok: true,
  dry_run: true,
  created: 2,
  updated: 1,
  failed: 0,
  skipped: 0,
  message: "ok",
  results: [],
  error_csv: null,
  ...over,
});

describe("importScreen", () => {
  it("names Commit as the primary CTA", () => {
    expect(PRIMARY_CTA).toBe("Commit");
  });

  it("steps Upload → Map → Validate → Commit from state", () => {
    expect(importStepFromState({ rowCount: 0, lastResult: null })).toBe(1);
    expect(importStepFromState({ rowCount: 3, lastResult: null })).toBe(2);
    expect(importStepFromState({ rowCount: 3, lastResult: baseResult({ dry_run: true }) })).toBe(3);
    expect(importStepFromState({ rowCount: 3, lastResult: baseResult({ dry_run: false }) })).toBe(4);
  });

  it("empty guide has what / why / next without em dashes", () => {
    const g = emptyImportGuide();
    expect(g.title.length).toBeGreaterThan(3);
    expect(g.why.length).toBeGreaterThan(3);
    expect(g.next.length).toBeGreaterThan(3);
    expect(`${g.title}${g.why}${g.next}`).not.toMatch(/\u2014|\u2013/);
  });

  it("error guides cover preview and commit contexts", () => {
    const preview = importErrorGuide("preview", "Connection timed out while parsing partners.csv");
    expect(preview.why.toLowerCase()).toMatch(/took too long|timeout/);
    expect(preview.next.toLowerCase()).toContain("parse");
    const commit = importErrorGuide("commit");
    expect(commit.next.toLowerCase()).toMatch(/retry|error csv/);
    expect(`${preview.title}${commit.next}`).not.toMatch(/\u2014|\u2013/);
  });

  it("detects unmapped columns and blocks commit until mapped", () => {
    const headers = ["name", "email"];
    expect(unmappedColumns({ name: "name", email: "" }, headers)).toEqual(["email"]);
    expect(mappingReady({ name: "name", email: "" }, headers)).toBe(true);
    expect(mappingReady({ name: "", email: "" }, headers)).toBe(false);
    expect(
      commitBlockedReason({ rowCount: 2, busy: false, headers, mapping: { name: "", email: "" } }),
    ).toMatch(/map at least one/i);
    expect(
      commitBlockedReason({ rowCount: 2, busy: false, headers, mapping: { name: "name", email: "email" } }),
    ).toBeNull();
  });

  it("builds test run count strip and partial failure guide", () => {
    const strip = countStripFromResult(
      baseResult({ failed: 2, created: 1, updated: 0, error_csv: "row,error\n1,x", dry_run: true }),
    );
    expect(strip.created).toBe(1);
    expect(strip.failed).toBe(2);
    expect(strip.hasErrorCsv).toBe(true);
    const guide = partialFailureGuide(strip);
    expect(guide?.title).toMatch(/would fail/);
    expect(guide?.next.toLowerCase()).toContain("error csv");
    expect(partialFailureGuide(countStripFromResult(baseResult()))).toBeNull();
  });

  it("sanitizes em dashes in operator copy", () => {
    expect(sanitizeImportCopy("Loaded seed — click Parse")).toBe("Loaded seed - click Parse");
  });

  it("folds test run honesty for the studio bar", () => {
    const g = importHonestyGuide();
    expect(g.title.toLowerCase()).toMatch(/[Tt]est run/);
    expect(`${g.title}${g.why}${g.next}`).not.toMatch(/\u2014|\u2013/);
    expect(importSessionBadge(1).label).toBe("Upload");
    expect(importSessionBadge(3).label).toBe("Validate");
    expect(importSessionHint({ lastResult: null })).toMatch(/Ready/);
    expect(
      importSessionHint({
        lastResult: baseResult({ dry_run: true }),
      }),
    ).toMatch(/No rows written/i);
  });
});
