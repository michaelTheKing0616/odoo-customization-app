/** Operator chips — never auto-confirmed connection/inferred plan rows. */

export type ReuseDecisionChip = {
  model?: string;
  confirmed?: boolean;
  source?: string;
};

/**
 * Snapshot restore / chip sync: only models the operator toggled, Confirmed,
 * or Installed. `connection` decisions are auto-confirmed on a live catalog and
 * must not become `operator_reuse` — that empties Suggested / Installable siblings.
 */
export function confirmedReuseModelsFromDraft(
  draft: Record<string, unknown> | null | undefined,
): string[] {
  if (!draft || typeof draft !== "object") return [];
  const reuse = draft.reuse as
    | { plan?: { decisions?: ReuseDecisionChip[] } }
    | undefined;
  const out: string[] = [];
  for (const d of reuse?.plan?.decisions ?? []) {
    if (!d?.model || !d.confirmed) continue;
    if (d.source === "operator" || d.source === "installable") {
      out.push(String(d.model));
    }
  }
  return Array.from(new Set(out));
}
