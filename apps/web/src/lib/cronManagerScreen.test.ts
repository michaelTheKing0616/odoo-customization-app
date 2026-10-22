import { describe, expect, it } from "vitest";
import {
  PRIMARY_CTA,
  cronErrorGuide,
  cronHonestyGuide,
  emptyCronGuide,
  formatCronNextRun,
  formatPreviewNextRun,
  intervalLabel,
  previewNextRunFromInterval,
  resolveCronStep,
  resolveCronTimeZone,
  sanitizeCronCopy,
} from "./cronManagerScreen";

describe("cronManagerScreen", () => {
  it("keeps Save the cron as the primary CTA copy", () => {
    expect(PRIMARY_CTA).toBe("Save the cron");
  });

  it("strips em and en dashes", () => {
    expect(sanitizeCronCopy("Enable — then trigger")).toBe("Enable - then trigger");
    expect(sanitizeCronCopy("a–b")).toBe("a-b");
  });

  it("resolves connection timezone from probe, else UTC honesty", () => {
    expect(resolveCronTimeZone({ tz: "Africa/Lagos" })).toEqual({
      timeZone: "Africa/Lagos",
      source: "connection",
      label: "Africa/Lagos",
    });
    const fallback = resolveCronTimeZone(null);
    expect(fallback.timeZone).toBe("UTC");
    expect(fallback.source).toBe("utc");
    expect(fallback.label).toContain("connection tz not reported");
  });

  it("formats nextcall in the given timezone", () => {
    const label = formatCronNextRun("2026-10-06 01:00:00", "UTC");
    expect(label).toMatch(/06 Oct 2026/);
    expect(formatCronNextRun(null, "UTC")).toBe("No next run scheduled");
  });

  it("previews next run from interval", () => {
    const now = new Date("2026-10-05T12:00:00Z");
    const next = previewNextRunFromInterval(1, "days", "UTC", now);
    expect(next.toISOString()).toBe("2026-10-06T12:00:00.000Z");
    expect(formatPreviewNextRun(1, "hours", "UTC", now)).toMatch(/05 Oct 2026/);
  });

  it("resolves stage from selection and compose", () => {
    expect(
      resolveCronStep({
        listHydrated: true,
        selectedCount: 0,
        hasTriggerResult: false,
        composing: false,
      }),
    ).toBe("list");
    expect(
      resolveCronStep({
        listHydrated: true,
        selectedCount: 2,
        hasTriggerResult: false,
        composing: false,
      }),
    ).toBe("select");
    expect(
      resolveCronStep({
        listHydrated: true,
        selectedCount: 1,
        hasTriggerResult: true,
        composing: false,
      }),
    ).toBe("trigger");
    expect(
      resolveCronStep({
        listHydrated: true,
        selectedCount: 0,
        hasTriggerResult: false,
        composing: true,
      }),
    ).toBe("save");
  });

  it("provides what/why/next honesty and empty guides", () => {
    const honesty = cronHonestyGuide();
    expect(honesty.title.toLowerCase()).toContain("enable");
    expect(honesty.why.toLowerCase()).toContain("test run");
    expect(emptyCronGuide().next.toLowerCase()).toContain("save the cron");
  });

  it("classifies timeout errors", () => {
    const guide = cronErrorGuide("load", "Connection timed out while listing crons");
    expect(guide.why).toMatch(/took too long/i);
    expect(guide.next).toMatch(/open Cron Manager again/i);
  });

  it("labels intervals", () => {
    expect(intervalLabel(1, "days")).toBe("Every 1 day");
    expect(intervalLabel(2, "hours")).toBe("Every 2 hours");
  });
});
