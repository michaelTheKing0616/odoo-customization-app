import { describe, expect, it } from "vitest";
import type { JobRow } from "./api";
import {
  draftFromJobResult,
  pickCachedDraft,
  pickRecoverableDraft,
  resolveJobDraftOutcome,
  visibleDraftWarnings,
} from "./draft-job-outcome";

function job(partial: Partial<JobRow> & Pick<JobRow, "status">): JobRow {
  return {
    id: "job-1",
    kind: "ai_draft",
    connection_id: "conn-1",
    result: null,
    error: null,
    created_at: null,
    finished_at: null,
    ...partial,
  };
}

describe("draftFromJobResult", () => {
  it("prefers result.draft over partial_draft", () => {
    const row = job({
      status: "timeout",
      result: {
        draft: { technical_name: "final" },
        partial_draft: { technical_name: "seed" },
      },
    });
    expect(draftFromJobResult(row)?.technical_name).toBe("final");
  });

  it("falls back to partial_draft", () => {
    const row = job({
      status: "timeout",
      result: { partial_draft: { technical_name: "seed" } },
    });
    expect(draftFromJobResult(row)?.technical_name).toBe("seed");
  });
});

describe("resolveJobDraftOutcome", () => {
  it("treats timeout with saved JSON as a recoverable draft", () => {
    const outcome = resolveJobDraftOutcome(
      job({
        status: "timeout",
        error: "Job exceeded 1800s limit",
        result: { partial_draft: { technical_name: "law_firm_management" } },
      }),
      "ok",
    );
    expect(outcome.kind).toBe("partial");
    if (outcome.kind === "partial") {
      expect(outcome.draft.technical_name).toBe("law_firm_management");
      expect(outcome.note).toMatch(/Saved snapshots/i);
    }
  });

  it("uses a host note for component drafts instead of domain pack", () => {
    const outcome = resolveJobDraftOutcome(
      job({
        status: "succeeded",
        result: {
          draft: {
            _component: true,
            connect_points: { host_label: "Invoicing", host_model: "account.move" },
          },
          warnings: ["live_apply: contract ready", "senior: date activity on account.move"],
        },
      }),
    );
    expect(outcome.kind).toBe("succeeded");
    if (outcome.kind === "succeeded") {
      expect(outcome.note).toMatch(/Invoicing/);
      expect(outcome.note).not.toMatch(/domain pack/i);
      expect(outcome.warnings).toEqual([]);
    }
  });

    it("uses a stock-reuse note instead of Apply-on-host copy", () => {
      const outcome = resolveJobDraftOutcome(
        job({
          status: "succeeded",
          result: {
            draft: {
              _generation_engine: { capability: "stock_reuse" },
              models: [],
            },
          },
        }),
      );
      expect(outcome.kind).toBe("succeeded");
      if (outcome.kind === "succeeded") {
        expect(outcome.note).toMatch(/Job Autopilot/i);
        expect(outcome.note).not.toMatch(/Invoicing/);
      }
    });

  it("fails timeout only when no JSON was saved", () => {
    const outcome = resolveJobDraftOutcome(
      job({ status: "timeout", error: "Job exceeded 1800s limit" }),
      "ok",
    );
    expect(outcome.kind).toBe("failed");
    if (outcome.kind === "failed") {
      expect(outcome.error).toMatch(/1800s/);
    }
  });
});

describe("pickCachedDraft", () => {
  it("prefers the cache row whose prompt matches", () => {
    const draft = pickCachedDraft(
      [
        { id: "a", prompt: "restaurant brief", draft: { technical_name: "kitchen" } },
        { id: "b", prompt: "law firm", draft: { technical_name: "law_firm_management" } },
      ],
      "law firm",
    );
    expect(draft?.technical_name).toBe("law_firm_management");
  });

  it("does not restore a hotel pack for an office visitor-log prompt", () => {
    const visitor =
      "Front desk still uses a paper book. I want a simple visitor log in Odoo.";
    const draft = pickCachedDraft(
      [
        {
          id: "hotel",
          prompt: visitor,
          draft: {
            technical_name: "hotel_management",
            domain_pack: "hotel",
            models: [{ model: "x_hotel" }],
          },
        },
      ],
      visitor,
    );
    expect(draft).toBeNull();
  });

  it("still restores a hotel pack when the prompt is lodging", () => {
    const prompt = "Hotel PMS front desk check-in with housekeeping";
    const draft = pickCachedDraft(
      [
        {
          id: "hotel",
          prompt,
          draft: { technical_name: "hotel_management", domain_pack: "hotel" },
        },
      ],
      prompt,
    );
    expect(draft?.technical_name).toBe("hotel_management");
  });

  it("does not fall back to the newest snapshot for a different prompt", () => {
    const draft = pickCachedDraft(
      [
        {
          id: "new",
          prompt: "law firm matters",
          draft: { technical_name: "law_firm_management" },
        },
      ],
      "visitor log at reception",
    );
    expect(draft).toBeNull();
  });
});

describe("pickRecoverableDraft", () => {
  it("ignores a streamed hotel partial for a visitor-log prompt", () => {
    const visitor =
      "Front desk still uses a paper book. I want a simple visitor log in Odoo.";
    const draft = pickRecoverableDraft(
      { technical_name: "hotel_management", domain_pack: "hotel" },
      [
        {
          id: "hotel",
          prompt: visitor,
          draft: { technical_name: "hotel_management", domain_pack: "hotel" },
        },
      ],
      visitor,
    );
    expect(draft).toBeNull();
  });
});

describe("visibleDraftWarnings", () => {
  it("drops senior: and non-gap live_apply rows", () => {
    expect(
      visibleDraftWarnings([
        "senior: skip",
        "live_apply: mixins ok",
        "live_apply: gap on next_activity",
        "pack merge warning",
      ]),
    ).toEqual(["live_apply: gap on next_activity", "pack merge warning"]);
  });
});
