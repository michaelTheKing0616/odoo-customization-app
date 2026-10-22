import { describe, expect, it } from "vitest";
import {
  EXPERT_HONESTY_LINE,
  EXPERT_STARTER_PROMPTS,
  expertComposerPlaceholder,
  expertEmptyBody,
  expertEmptyTitle,
  expertHeaderDescription,
  expertHonestyLegend,
  expertOverviewBody,
  expertSessionHint,
  formatExpertContextLabel,
  isExpertDestinationPath,
} from "./expert-journey";
import { expertCautionDescription, formatExpertCautionFlag } from "./expert-caution-flags";

const FLAGS = [
  "legal_tax_deflection",
  "low_retrieval",
  "pcm_consistent_refusal",
  "instance_caveats",
  "rule_based_diagnosis",
  "rule_based_stack_guidance",
  "inferred_stack",
  "access",
  "protected_:account.move",
];

describe("Expert copy (UI-S-25)", () => {
  it("has no em or en dashes in Expert UI copy", () => {
    const copy = [
      EXPERT_HONESTY_LINE,
      expertHeaderDescription("Lab 19"),
      expertEmptyTitle(),
      expertEmptyBody(),
      expertOverviewBody(),
      expertComposerPlaceholder(),
      ...expertHonestyLegend(),
      ...EXPERT_STARTER_PROMPTS.flatMap((p) => [p.label, p.question]),
      ...FLAGS.flatMap((f) => [formatExpertCautionFlag(f) ?? "", expertCautionDescription(f) ?? ""]),
    ];
    for (const line of copy) {
      expect(line, line).not.toMatch(/[\u2013\u2014]/);
    }
  });

  it("keeps the honesty contract in the empty state and overview", () => {
    expect(expertEmptyBody()).toMatch(/not Job Autopilot/);
    expect(expertOverviewBody()).toMatch(/never applies an app plan/);
    expect(EXPERT_HONESTY_LINE).toBe("A complete draft is not the same as certified, and neither means Autopilot-ready. Expert never publishes on its own.");
  });
});

describe("isExpertDestinationPath", () => {
  it("matches only the dedicated Expert route", () => {
    expect(isExpertDestinationPath("/connections/c1/expert")).toBe(true);
    expect(isExpertDestinationPath("/connections/c1/expert/")).toBe(true);
    expect(isExpertDestinationPath("/connections/c1")).toBe(false);
    expect(isExpertDestinationPath("/connections/c1/expert/history")).toBe(false);
    expect(isExpertDestinationPath("/e2e/expert")).toBe(false);
    expect(isExpertDestinationPath(null)).toBe(false);
  });
});

describe("Expert context bar copy", () => {
  it("says plainly whether page context is shared", () => {
    expect(expertSessionHint({ contextEnabled: false, contextLabel: null })).toBe("Not shared");
    expect(expertSessionHint({ contextEnabled: true, contextLabel: null })).toBe(
      "Nothing to share on this page",
    );
  });

  it("does not report the Expert route itself as page context", () => {
    expect(formatExpertContextLabel({ route: "/connections/c1/expert" }, true)).toBeNull();
    expect(
      formatExpertContextLabel({ route: "/connections/c1/expert", model: "res.partner" }, true),
    ).toBe("res.partner");
    expect(formatExpertContextLabel({ route: "/connections/c1/builder" }, true)).toBe("builder");
  });
});
