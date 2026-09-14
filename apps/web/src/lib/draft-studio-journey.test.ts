import { describe, expect, it } from "vitest";
import {
  createDraftHint,
  draftNeedsRegenerate,
  draftStudioErrorTitle,
  draftStudioJourneyFromState,
  draftStudioJourneyHint,
  goLiveReadyFromDraft,
  scorecardBodyCopy,
  scorecardFromDraft,
  scorecardHeadline,
} from "./draft-studio-journey";

describe("draftStudioJourneyFromState", () => {
  it("maps prompt → enrich → review → apply without mixing App Studio ids", () => {
    expect(draftStudioJourneyFromState({}).id).toBe("prompt");
    expect(draftStudioJourneyFromState({ generating: true }).id).toBe("enrich");
    expect(draftStudioJourneyFromState({ hasDraft: true }).id).toBe("review");
    expect(draftStudioJourneyFromState({ hasDraft: true, applied: true })).toEqual({
      id: "apply",
      applied: true,
    });
    expect(draftStudioJourneyFromState({ generating: true, hasDraft: true }).id).toBe(
      "enrich",
    );
  });

  it("marks enrich failed when generation dies before a draft exists", () => {
    expect(draftStudioJourneyFromState({ failed: true })).toEqual({
      id: "enrich",
      failed: true,
    });
  });
});

describe("draftStudioJourneyHint", () => {
  it("keeps Completeness / Cert / Promote honesty on enrich and review", () => {
    expect(draftStudioJourneyHint({ id: "enrich" })).toMatch(/Completeness is not Cert/i);
    expect(draftStudioJourneyHint({ id: "enrich" })).toMatch(/Promote stays human/i);
    expect(draftStudioJourneyHint({ id: "review" })).toMatch(/hygiene/i);
    expect(draftStudioJourneyHint({ id: "review" })).toMatch(/Promote/i);
    expect(draftStudioJourneyHint({ id: "apply" })).toMatch(/View Designer/i);
    expect(draftStudioJourneyHint({ id: "prompt" })).toMatch(/nothing writes to Odoo/i);
  });
});

describe("draftNeedsRegenerate", () => {
  it("flags pack fallback and seeded depth, not a clean llm_full draft", () => {
    expect(draftNeedsRegenerate({ _llm_status: { mode: "pack_fallback" } })).toBe(true);
    expect(
      draftNeedsRegenerate({
        _llm_status: { mode: "seed_fallback" },
        _depth: { seeded: true },
      }),
    ).toBe(true);
    expect(draftNeedsRegenerate({ _llm_status: { mode: "llm_full" } })).toBe(false);
    expect(
      draftNeedsRegenerate({ _llm_status: { mode: "llm_full" } }, [
        "field-deepen skipped for timeout",
      ]),
    ).toBe(true);
  });
});

describe("scorecardHeadline", () => {
  it("never fuses Completeness with Certification or Autopilot", () => {
    expect(
      scorecardHeadline({
        score: 7.2,
        validatorsGreen: true,
        certTier: "ReviewRequired",
      }),
    ).toBe("Completeness: 7.2/10 · validators green · Cert: ReviewRequired");
    expect(scorecardHeadline({ score: 10, stockReuse: true })).toMatch(/Stock coverage/);
    expect(scorecardHeadline({ score: 10, stockReuse: true })).not.toMatch(/Autopilot/);
  });
});

describe("scorecardBodyCopy", () => {
  it("keeps empty-spec honesty for stock reuse", () => {
    expect(scorecardBodyCopy({ stockReuse: true })).toMatch(/Completeness ≠ Cert ≠ Autopilot/);
    expect(scorecardBodyCopy({ certShipReady: true, goLiveReady: true })).toMatch(
      /human promote/,
    );
  });
});

describe("createDraftHint", () => {
  it("asks for connect-point approval before Create draft on component grain", () => {
    expect(
      createDraftHint({
        promptLength: 40,
        needsConnectReview: true,
        connectReady: false,
      }),
    ).toMatch(/Review connect points/);
  });
});

describe("draftStudioErrorTitle", () => {
  it("names the failed step instead of a generic went-wrong title", () => {
    expect(draftStudioErrorTitle("Sandbox validate failed")).toBe("Sandbox validate failed");
    expect(draftStudioErrorTitle("")).toBe("Draft Studio request failed");
  });
});

describe("scorecard accessors", () => {
  it("reads scorecard and go-live flags from draft JSON", () => {
    const draft = {
      _scorecard: { score_0_10: 8.1, validators: { all_green: true } },
      _live_apply: { go_live_ready: true, done_bar: { mode: "sandbox" } },
    };
    expect(scorecardFromDraft(draft)?.score_0_10).toBe(8.1);
    expect(goLiveReadyFromDraft(draft)).toBe(true);
  });
});
