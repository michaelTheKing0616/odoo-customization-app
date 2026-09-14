/** Operator chips — never auto-confirmed connection/inferred plan rows. */

export type ReuseDecisionChip = {
  model?: string;
  reason?: string;
  confirmed?: boolean;
  source?: string;
  link_only?: boolean;
  module?: string;
};

function reusePlanDecisions(
  draft: Record<string, unknown> | null | undefined,
): ReuseDecisionChip[] {
  if (!draft || typeof draft !== "object") return [];
  const reuse = draft.reuse as { plan?: { decisions?: ReuseDecisionChip[] } } | undefined;
  return Array.isArray(reuse?.plan?.decisions) ? reuse.plan.decisions : [];
}

export function inferredReuseSuggestions(
  draft: Record<string, unknown> | null | undefined,
  rejected: string[] = [],
): ReuseDecisionChip[] {
  return reusePlanDecisions(draft).filter(
    (d) =>
      Boolean(d.model) &&
      !d.confirmed &&
      !rejected.includes(String(d.model)) &&
      (d.source === "inferred" || d.source === "pack_reuse_stock"),
  );
}

export function installableReuseSuggestions(
  draft: Record<string, unknown> | null | undefined,
  rejected: string[] = [],
): ReuseDecisionChip[] {
  return reusePlanDecisions(draft).filter(
    (d) =>
      Boolean(d.model) &&
      !d.confirmed &&
      !rejected.includes(String(d.model)) &&
      d.source === "installable",
  );
}

export function autoWiredReuseDecisions(
  draft: Record<string, unknown> | null | undefined,
): ReuseDecisionChip[] {
  return reusePlanDecisions(draft).filter(
    (d) =>
      Boolean(d.model) &&
      d.confirmed &&
      d.link_only &&
      (d.source === "apply_readiness" ||
        d.source === "pack_reuse_stock" ||
        d.source === "inferred"),
  );
}

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
