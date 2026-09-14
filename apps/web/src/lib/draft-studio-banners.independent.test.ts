import { describe, expect, it } from "vitest";
import { displayedCertificationTier } from "./draft-studio-banners";

/**
 * Independent CHECKER: wizard cert display vs live-apply.
 * Completeness ≠ Certification ≠ Autopilot. Never show Production when live-apply is ReviewRequired.
 */
describe("displayedCertificationTier (independent honesty IR)", () => {
  it("never shows Cert Production if live_apply certification_tier is ReviewRequired", () => {
    expect(
      displayedCertificationTier({
        _certification: { tier: "Production" },
        _live_apply: { certification_tier: "ReviewRequired" },
      }),
    ).toBe("ReviewRequired");
  });

  it("never shows Gold when live-apply is ReviewRequired", () => {
    expect(
      displayedCertificationTier({
        _certification: { tier: "Gold" },
        _live_apply: { certification_tier: "ReviewRequired" },
      }),
    ).toBe("ReviewRequired");
  });

  it("lets a lower live-apply rank win over a higher scorecard cert", () => {
    expect(
      displayedCertificationTier({
        _certification: { tier: "Production" },
        _live_apply: { certification_tier: "Reject" },
      }),
    ).toBe("Reject");
  });

  it("caps stock_reuse Production/Gold to ReviewRequired even without a live stamp", () => {
    expect(
      displayedCertificationTier({
        technical_name: "stock_reuse",
        _generation_engine: { capability: "stock_reuse" },
        _certification: { tier: "Production" },
      }),
    ).toBe("ReviewRequired");
    expect(
      displayedCertificationTier({
        _generation_engine: { capability: "stock_reuse" },
        _certification: { tier: "Gold" },
      }),
    ).toBe("ReviewRequired");
  });

  it("keeps ReviewRequired when both cert and live-apply agree", () => {
    expect(
      displayedCertificationTier({
        _certification: { tier: "ReviewRequired" },
        _live_apply: { certification_tier: "ReviewRequired" },
      }),
    ).toBe("ReviewRequired");
  });
});
