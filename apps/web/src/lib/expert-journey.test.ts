import { describe, expect, it } from "vitest";
import {
  EXPERT_HONESTY_LINE,
  EXPERT_STARTER_PROMPTS,
  expertEmptyBody,
  expertGroundingLabel,
  expertHeaderDescription,
  expertHonestyLegend,
  expertOverviewBody,
  expertSessionHint,
  formatExpertContextLabel,
  linkifyCitationMarkers,
  splitUserTurnForDisplay,
} from "./expert-journey";

describe("expert-journey", () => {
  it("never claims auto-promote or fused Completeness/Cert/Autopilot", () => {
    const blobs = [
      EXPERT_HONESTY_LINE,
      expertHeaderDescription("Lab 19"),
      expertEmptyBody(),
      expertOverviewBody(),
      expertSessionHint({ contextEnabled: true, contextLabel: "res.partner" }),
      ...expertHonestyLegend(),
    ].join(" ");
    expect(blobs).toMatch(/Completeness ≠ Cert ≠ Autopilot/);
    expect(blobs).toMatch(/never auto-promote/i);
    expect(blobs).not.toMatch(/will auto-promote/i);
    expect(blobs).not.toMatch(/Expert will promote/i);
  });

  it("names the connection in the Expert destination header", () => {
    expect(expertHeaderDescription("Lab 19")).toMatch(/^Lab 19 · /);
    expect(expertHeaderDescription(null)).toMatch(/^Grounded answers/);
  });

  it("formats page context without inventing fields", () => {
    expect(
      formatExpertContextLabel(
        { model: "res.partner", field: "email", route: "/connections/c1/builder" },
        true,
      ),
    ).toBe("res.partner · email · builder");
    expect(formatExpertContextLabel({ model: "x_matter" }, false)).toBeNull();
  });

  it("labels grounded / declined / uncited honestly", () => {
    expect(expertGroundingLabel({ declined: true, grounded: false, uncited_warning: false })).toEqual({
      label: "Declined",
      variant: "warning",
    });
    expect(expertGroundingLabel({ declined: false, grounded: true, uncited_warning: false })).toEqual({
      label: "Grounded",
      variant: "success",
    });
    expect(expertGroundingLabel({ declined: false, grounded: true, uncited_warning: true })?.label).toMatch(
      /uncited/,
    );
    expect(expertGroundingLabel({ declined: false, grounded: false, uncited_warning: false })?.label).toBe(
      "Ungrounded",
    );
  });

  it("linkifies citation markers without touching markdown links", () => {
    expect(linkifyCitationMarkers("See ACL [1] and [docs](https://odoo.com).")).toBe(
      "See ACL [1](#cite-1) and [docs](https://odoo.com).",
    );
  });

  it("splits diagnose turns so the error log is not a raw dump", () => {
    const split = splitUserTurnForDisplay("Diagnose this\n\nError log:\nAccessError: denied");
    expect(split.question).toBe("Diagnose this");
    expect(split.errorLog).toBe("AccessError: denied");
    expect(splitUserTurnForDisplay("Plain question").errorLog).toBeNull();
  });

  it("keeps starter prompts as inbound questions, not apply/promote actions", () => {
    expect(EXPERT_STARTER_PROMPTS.length).toBeGreaterThan(0);
    const joined = EXPERT_STARTER_PROMPTS.map((p) => `${p.label} ${p.question}`).join(" ");
    expect(joined.toLowerCase()).not.toMatch(/auto-promote|generate ui|apply now/);
  });
});
