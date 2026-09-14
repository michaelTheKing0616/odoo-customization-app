import { describe, expect, it } from "vitest";
import {
  draftEnrichmentClean,
  draftHasUnguardedCreateGate,
  llmStatusBannerCopy,
  showRetryEnrichment,
  withEnrichmentCleanFlags,
} from "./draft-llm-status";

const punch = {
  models: [
    {
      model: "x_punch_card",
      fields: [
        {
          name: "x_last_transaction_id",
          ttype: "many2one",
          relation: "pos.order",
        },
      ],
    },
  ],
  _llm_status: {
    mode: "llm_full",
    failed_steps: [],
  },
};

describe("draftEnrichmentClean", () => {
  it("trusts enrichment_clean true", () => {
    expect(
      draftEnrichmentClean({
        _llm_status: { mode: "llm_full", enrichment_clean: true },
      }),
    ).toBe(true);
  });

  it("keeps Retry on when unguarded pos.order and flags omitted", () => {
    expect(draftHasUnguardedCreateGate(punch)).toBe(true);
    expect(draftEnrichmentClean(punch)).toBe(false);
  });

  it("treats llm_full with omitted flags as clean when gates are stamped", () => {
    const gated = {
      ...punch,
      models: [
        {
          model: "x_punch_card",
          fields: [
            {
              name: "x_last_transaction_id",
              relation: "pos.order",
              options: { no_create: true, no_create_edit: true },
            },
          ],
        },
      ],
    };
    expect(draftEnrichmentClean(gated)).toBe(true);
    const stamped = withEnrichmentCleanFlags(gated);
    expect((stamped._llm_status as { enrichment_clean?: boolean }).enrichment_clean).toBe(
      true,
    );
  });

  it("respects retry_recommended true", () => {
    expect(
      draftEnrichmentClean({
        _llm_status: {
          mode: "llm_full",
          failed_steps: [],
          retry_recommended: true,
        },
      }),
    ).toBe(false);
  });
});

describe("llmStatusBannerCopy", () => {
  it("keeps wizard pack-fallback copy and hides on stock_reuse", () => {
    expect(
      llmStatusBannerCopy({
        draft: { _llm_status: { mode: "pack_fallback" } },
      }),
    ).toMatch(/domain pack/);
    expect(
      llmStatusBannerCopy({
        draft: { _llm_status: { mode: "llm_full" } },
        stockReuse: true,
      }),
    ).toBeNull();
    expect(
      llmStatusBannerCopy({
        draft: { _llm_status: { mode: "llm_full" } },
        retryDisabled: true,
      }),
    ).toMatch(/completed successfully/);
  });

  it("does not offer Retry on component drafts", () => {
    expect(showRetryEnrichment({ draft: { _component: true } })).toBe(false);
    expect(showRetryEnrichment({ draft: { models: [] } })).toBe(true);
  });
});
