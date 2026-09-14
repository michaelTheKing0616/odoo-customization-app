import { describe, expect, it } from "vitest";
import {
  progressLabelFromJob,
  studioErrorTitle,
  studioJourneyFromPhase,
  studioJourneyHint,
} from "./studio-journey";

describe("studioJourneyFromPhase", () => {
  it("maps session phases onto the elite brief-to-apply rail", () => {
    expect(studioJourneyFromPhase({ phase: "prompt" }).id).toBe("brief");
    expect(studioJourneyFromPhase({ phase: "clarify" }).id).toBe("clarify");
    expect(studioJourneyFromPhase({ phase: "generating" }).id).toBe("generate");
    expect(studioJourneyFromPhase({ phase: "failed" })).toEqual({
      id: "generate",
      failed: true,
    });
    expect(studioJourneyFromPhase({ phase: "review" }).id).toBe("review");
    expect(studioJourneyFromPhase({ phase: "review", applied: true })).toEqual({
      id: "apply",
      applied: true,
    });
  });
});

describe("studioJourneyHint", () => {
  it("keeps Completeness / Cert / Promote honesty on generate and review", () => {
    expect(studioJourneyHint({ id: "generate" })).toMatch(/Completeness is not Cert/i);
    expect(studioJourneyHint({ id: "generate" })).toMatch(/Promote stays human/i);
    expect(studioJourneyHint({ id: "review" })).toMatch(/sandbox/i);
    expect(studioJourneyHint({ id: "apply" })).toMatch(/View Designer/i);
  });
});

describe("progressLabelFromJob", () => {
  it("prefers stage labels and strips Stage A prefixes", () => {
    expect(
      progressLabelFromJob({
        id: "j1",
        kind: "ai_draft",
        connection_id: null,
        status: "running",
        result: { step_label: "Stage B · Authoring Option A module" },
        error: null,
        created_at: null,
        finished_at: null,
      }),
    ).toMatch(/Authoring Option A module/);
  });

  it("falls back to queued / building copy", () => {
    expect(
      progressLabelFromJob({
        id: "j1",
        kind: "ai_draft",
        connection_id: null,
        status: "queued",
        result: null,
        error: null,
        created_at: null,
        finished_at: null,
      }),
    ).toBe("Queued");
    expect(progressLabelFromJob(null)).toBe("Building your draft");
  });
});

describe("studioErrorTitle", () => {
  it("names the failed step instead of a generic went-wrong title", () => {
    expect(studioErrorTitle("Generation failed")).toBe("Generation failed");
    expect(studioErrorTitle("Sandbox prove failed")).toBe("Sandbox prove failed");
    expect(studioErrorTitle("")).toBe("App Studio request failed");
  });
});
