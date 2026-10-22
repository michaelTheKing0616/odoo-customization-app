import { describe, expect, it } from "vitest";
import {
  APPLY_CTA,
  PRIMARY_CTA,
  applyBlockedReason,
  downloadBlockedReason,
  emptyCellDisplay,
  emptyIdGenGuide,
  formatCodeExample,
  idGenErrorGuide,
  idGenHonestyGuide,
  idGenStepFromState,
  previewCountsGuide,
  sanitizeIdGenCopy,
  sequenceHonestyGuide,
} from "@/lib/idGeneratorScreen";

describe("idGeneratorScreen", () => {
  it("names Download updated CSV as the primary CTA", () => {
    expect(PRIMARY_CTA).toBe("Download updated CSV");
    expect(APPLY_CTA).toBe("Apply codes");
  });

  it("steps Source → Rules → Preview → Deliver from state", () => {
    expect(
      idGenStepFromState({ mode: "csv", hasSource: false, hasPreview: false, delivered: false }),
    ).toBe(1);
    expect(
      idGenStepFromState({ mode: "csv", hasSource: true, hasPreview: false, delivered: false }),
    ).toBe(2);
    expect(
      idGenStepFromState({ mode: "csv", hasSource: true, hasPreview: true, delivered: false }),
    ).toBe(3);
    expect(
      idGenStepFromState({ mode: "live", hasSource: true, hasPreview: true, delivered: true }),
    ).toBe(4);
  });

  it("empty guides cover csv and live what/why/next without em dashes", () => {
    const csv = emptyIdGenGuide("csv");
    const live = emptyIdGenGuide("live");
    for (const g of [csv, live, idGenHonestyGuide(), sequenceHonestyGuide(true), sequenceHonestyGuide(false)]) {
      const blob = `${g.title} ${g.why} ${g.next}`;
      expect(blob).not.toMatch(/[\u2014\u2013]/);
      expect(g.why.length).toBeGreaterThan(10);
      expect(g.next.length).toBeGreaterThan(10);
    }
  });

  it("honesty states preview never writes and sequence is separate", () => {
    const h = idGenHonestyGuide();
    expect(h.title.toLowerCase()).toMatch(/never write/);
    expect(h.why.toLowerCase()).toMatch(/ir\.sequence/);
    const on = sequenceHonestyGuide(true);
    expect(on.why.toLowerCase()).toMatch(/after/);
    expect(on.title.toLowerCase()).toMatch(/after apply|sequence bridge/);
  });

  it("blocks download and apply for the wrong mode or missing preview", () => {
    expect(downloadBlockedReason({ mode: "live", hasCsvPreview: true, busy: false })).toMatch(/Switch to CSV/);
    expect(downloadBlockedReason({ mode: "csv", hasCsvPreview: false, busy: false })).toMatch(/Preview CSV/);
    expect(downloadBlockedReason({ mode: "csv", hasCsvPreview: true, busy: false })).toBeNull();
    expect(applyBlockedReason({ mode: "csv", busy: false, hasDryRun: true })).toMatch(/Switch to Live/);
    expect(applyBlockedReason({ mode: "live", busy: false, hasDryRun: false })).toMatch(/Test run/);
    expect(applyBlockedReason({ mode: "live", busy: false, hasDryRun: true })).toBeNull();
  });

  it("formats a sample code and empty cells without em dashes", () => {
    expect(formatCodeExample({ prefix: "inv", separator: "-", padding: 4, initialsLength: 3 })).toBe(
      "INV-ATC-0001",
    );
    expect(emptyCellDisplay(null)).toBe("none");
    expect(emptyCellDisplay("  ")).toBe("none");
    expect(emptyCellDisplay("AB-01")).toBe("AB-01");
    expect(sanitizeIdGenCopy("a\u2014b\u2013c")).toBe("a-b-c");
  });

  it("preview counts and errors stay dash-free", () => {
    const counts = previewCountsGuide({
      total: 10,
      changed: 3,
      skipped: 7,
      dryRun: true,
      mode: "live",
    });
    expect(counts.title).toMatch(/3 changes of 10/);
    expect(counts.why).toMatch(/Nothing was written/);
    const err = idGenErrorGuide("live_apply", "timed out\u2014gateway");
    expect(`${err.title}${err.why}${err.next}`).not.toMatch(/[\u2014\u2013]/);
    expect(err.next.toLowerCase()).toMatch(/risk phrase|retry/);
  });
});
