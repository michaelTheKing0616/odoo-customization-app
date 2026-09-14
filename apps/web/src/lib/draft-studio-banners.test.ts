import { describe, expect, it } from "vitest";
import { SCORE_BARS } from "./copy-guide";
import {
  displayedCertificationTier,
  expertCloserHint,
  expertShouldRepair,
  liveApplyGapBanner,
  unfinishedDraftBanner,
} from "./draft-studio-banners";

describe("draft-studio-banners", () => {
  it("does not invent live-apply gaps on stock_reuse ready:false with empty findings", () => {
    const draft = {
      _generation_engine: { capability: "stock_reuse" },
      _scorecard: { score_0_10: 10, findings: [] },
      _live_apply: { ready: false, findings: [] },
    };
    expect(liveApplyGapBanner(draft)).toBeNull();
    expect(unfinishedDraftBanner(draft)).toBeNull();
    expect(expertShouldRepair(draft)).toBe(false);
    expect(expertCloserHint(draft)).toMatch(/Job Autopilot/);
  });

  it("does not claim missing dates when ready is false and findings are empty", () => {
    const draft = {
      _scorecard: { score_0_10: 10, findings: [] },
      _live_apply: { ready: false, findings: [] },
    };
    expect(liveApplyGapBanner(draft)).toBeNull();
    expect(expertShouldRepair(draft)).toBe(false);
    expect(expertCloserHint(draft)).toMatch(/leave this spec unchanged/);
  });

  it("quotes actual live-apply findings and recommends Expert", () => {
    const draft = {
      _scorecard: { score_0_10: 8, findings: [] },
      _live_apply: {
        ready: false,
        findings: [
          { detail: "live apply: next_activity needs mail.activity.mixin" },
        ],
      },
    };
    const banner = liveApplyGapBanner(draft);
    expect(banner?.testId).toBe("live-apply-not-ready");
    expect(banner?.body).toContain("mail.activity.mixin");
    expect(banner?.body).not.toContain("missing date fields or activity mixins");
    expect(expertShouldRepair(draft)).toBe(true);
    expect(expertCloserHint(draft)).toBe(SCORE_BARS.expertFix);
  });

  it("treats a scored residual without a quality-score gap as finished", () => {
    expect(
      unfinishedDraftBanner({
        _scorecard: { score_0_10: 8 },
        _live_apply: { ready: false },
      }),
    ).toBeNull();
  });

  it("never shows Production when live-apply cert is ReviewRequired", () => {
    expect(
      displayedCertificationTier({
        _certification: { tier: "Production" },
        _live_apply: { certification_tier: "ReviewRequired" },
      }),
    ).toBe("ReviewRequired");
  });
});
