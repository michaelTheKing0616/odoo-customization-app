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
