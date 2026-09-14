/** LLM enrichment status helpers for Draft Studio (Retry enable / success banner). */

export type LlmStatusBlock = {
  mode?: string;
  reason?: string;
  failed_steps?: string[];
  retry_recommended?: boolean;
  enrichment_clean?: boolean;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

/** True when an x_* many2one points at a create-gated host without no_create. */
export function draftHasUnguardedCreateGate(draft: unknown): boolean {
  const rec = asRecord(draft);
  if (!rec) return false;
  const gated = new Set(["pos.order", "pos.session", "pos.payment.method"]);
  const models = Array.isArray(rec.models) ? rec.models : [];
  for (const model of models) {
    if (!model || typeof model !== "object" || Array.isArray(model)) continue;
    const mid = String((model as { model?: string }).model || "");
    if (!mid.startsWith("x_")) continue;
    for (const field of (model as { fields?: unknown[] }).fields || []) {
      if (!field || typeof field !== "object" || Array.isArray(field)) continue;
      const f = field as {
        relation?: string;
        options?: { no_create?: boolean };
      };
      const rel = String(f.relation || "");
      if (!gated.has(rel)) continue;
      if (f.options?.no_create !== true) return true;
    }
  }
  return false;
}

/**
 * Whether Retry AI enrichment should be disabled after a successful clean run.
 * Prefer `_llm_status.enrichment_clean`; fall back when older APIs omit the flag.
 */
export function draftEnrichmentClean(draft: unknown): boolean {
  const rec = asRecord(draft);
  if (!rec) return false;
  const status = rec._llm_status as LlmStatusBlock | undefined;
  if (!status || typeof status !== "object") return false;
  if (status.enrichment_clean === true) return true;
  if (status.enrichment_clean === false) return false;
  if (status.retry_recommended === true) return false;
  if (status.mode !== "llm_full") return false;
  if ((status.failed_steps || []).length > 0) return false;
  if (draftHasUnguardedCreateGate(rec)) return false;
  // Older API omitted flags after a successful llm_full enrich.
  return true;
}

/** Stamp missing clean flags so snapshots / reloads keep Retry disabled. */
export function withEnrichmentCleanFlags(
  draft: Record<string, unknown>,
): Record<string, unknown> {
  if (!draftEnrichmentClean(draft)) return draft;
  const status = {
    ...((draft._llm_status as LlmStatusBlock | undefined) || {}),
    enrichment_clean: true,
    retry_recommended: false,
  };
  return { ...draft, _llm_status: status };
}

export function llmStatusFromDraft(draft: unknown): LlmStatusBlock | undefined {
  const rec = asRecord(draft);
  const status = rec?._llm_status;
  if (!status || typeof status !== "object" || Array.isArray(status)) return undefined;
  return status as LlmStatusBlock;
}

export function showRetryEnrichment(opts: {
  draft: unknown;
  stockReuse?: boolean;
  refuseClone?: boolean;
}): boolean {
  const rec = asRecord(opts.draft);
  if (!rec) return false;
  if (rec._component || opts.stockReuse || opts.refuseClone) return false;
  return true;
}

/**
 * Operator-facing enrichment copy. Wizard defaults — App Studio does not use this helper.
 */
export function llmStatusBannerCopy(opts: {
  draft: unknown;
  stockReuse?: boolean;
  retryDisabled?: boolean;
}): string | null {
  const rec = asRecord(opts.draft);
  if (!rec || rec._component || opts.stockReuse) return null;
  const status = llmStatusFromDraft(rec);
  const mode = status?.mode;
  const reason = status?.reason;
  const seeded = Boolean((rec._depth as { seeded?: boolean } | undefined)?.seeded);

  if (mode === "llm_partial") {
    return "Some AI steps timed out; the draft was finished from your prompt. Click Retry AI enrichment to wake AI, re-run missed steps, and complete residual fields from your brief if AI stays down.";
  }
  if (mode === "pack_fallback" && reason === "residual_recovered") {
    return "Residual completed from your brief (AI was unavailable). Review fields, then Apply — or Retry again when a model is back for LLM polish.";
  }
  if (
    mode === "pack_fallback" &&
    (reason === "timeout" || reason === "unavailable" || reason === "honesty_seed")
  ) {
    return "AI was unavailable on Create draft. Click Retry AI enrichment — it wakes Flash/local/cloud, re-runs missed AI steps, and still completes residual fields from your brief if AI stays down.";
  }
  if (mode === "pack_fallback") {
    return "Draft Studio used the domain pack. Click Retry AI enrichment to tailor when a model is available.";
  }
  if (mode === "seed_fallback" && seeded) {
    return "Depth targets were met via generic operational seeds — review entities before apply.";
  }
  if (mode === "llm_full" && opts.retryDisabled) {
    return "AI enrichment completed successfully. Retry stays available only if hygiene gaps return.";
  }
  if (mode === "llm_full") {
    return "AI draft finished. Retry AI enrichment to wake providers and collapse residual hygiene if needed.";
  }
  return null;
}
