/** Draft Studio journey stages — chrome only, not the generator. Distinct from App Studio. */

export const DRAFT_STUDIO_STAGES = [
  { id: "prompt", label: "Prompt" },
  { id: "enrich", label: "Enrich" },
  { id: "review", label: "Review" },
  { id: "apply", label: "Apply" },
] as const;

export type DraftStudioJourneyId = (typeof DRAFT_STUDIO_STAGES)[number]["id"];

export type DraftStudioJourneyState = {
  id: DraftStudioJourneyId;
  failed?: boolean;
  applied?: boolean;
};

export type DraftScorecard = {
  score_0_10?: number;
  dimensions?: Record<string, number>;
  findings?: Array<{ dimension?: string; element?: string; detail?: string }>;
  validators?: { all_green?: boolean; xml_ok?: boolean; consistency_ok?: boolean };
};

export type DraftCertification = {
  tier?: string;
  quality?: number;
  evidence?: number;
  risk?: number;
  hard_failures?: string[];
  option_a_pending?: boolean;
  note?: string;
};

export type DraftDoneBar = {
  mode?: string;
  next_step?: string;
  go_live_ready?: boolean;
};

export function draftStudioJourneyFromState(opts: {
  generating?: boolean;
  hasDraft?: boolean;
  applied?: boolean;
  failed?: boolean;
}): DraftStudioJourneyState {
  if (opts.generating) return { id: "enrich", failed: Boolean(opts.failed) };
  if (opts.failed && !opts.hasDraft) return { id: "enrich", failed: true };
  if (opts.applied && opts.hasDraft) return { id: "apply", applied: true };
  if (opts.hasDraft) return { id: "review" };
  return { id: "prompt" };
}

export function draftStudioJourneyHint(state: DraftStudioJourneyState): string {
  if (state.failed) {
    return "Draft did not finish. Retry enrichment, or create the draft again. Promote stays human.";
  }
  switch (state.id) {
    case "prompt":
      return "Describe a field, a feature, or a full app. Create draft builds a ModuleSpec — nothing writes to Odoo yet.";
    case "enrich":
      return "Quality pass is running. Completeness is not Cert. Promote stays human.";
    case "review":
      return "Scorecard is ModuleSpec hygiene, not go-live. Apply writes live metadata. Zip, sandbox, then Promote.";
    case "apply":
      return "Live on this connection. Open in Odoo, or View Designer for the primary form.";
  }
}

export function draftNeedsRegenerate(
  draft: Record<string, unknown> | null | undefined,
  warnings: string[] = [],
): boolean {
  if (!draft) return false;
  const mode = (draft._llm_status as { mode?: string } | undefined)?.mode;
  if (mode === "llm_partial" || mode === "pack_fallback") return true;
  const seeded = Boolean((draft._depth as { seeded?: boolean } | undefined)?.seeded);
  if (seeded && mode === "seed_fallback") return true;
  return warnings.some(
    (w) => w.includes("field-deepen skipped") || w.includes("depth met via generic seeds"),
  );
}

export function draftStudioErrorTitle(message: string | null | undefined): string {
  const text = (message || "").trim();
  if (!text) return "Draft Studio request failed";
  if (/enrich/i.test(text)) return "Enrichment failed";
  if (/draft|generat/i.test(text)) return "Draft failed";
  if (/zip|export/i.test(text)) return "Zip export failed";
  if (/sandbox|prove|validat/i.test(text)) return "Sandbox validate failed";
  if (/promote/i.test(text)) return "Promote failed";
  if (/apply/i.test(text)) return "Apply failed";
  if (/scaffold/i.test(text)) return "Scaffold failed";
  return "Draft Studio request failed";
}

export function scorecardFromDraft(
  draft: Record<string, unknown> | null | undefined,
): DraftScorecard | undefined {
  const card = draft?._scorecard;
  if (!card || typeof card !== "object" || Array.isArray(card)) return undefined;
  return card as DraftScorecard;
}

export function certificationFromDraft(
  draft: Record<string, unknown> | null | undefined,
): DraftCertification | undefined {
  const row = draft?._certification;
  if (!row || typeof row !== "object" || Array.isArray(row)) return undefined;
  return row as DraftCertification;
}

export function doneBarFromDraft(
  draft: Record<string, unknown> | null | undefined,
): DraftDoneBar | undefined {
  const direct = draft?._done_bar;
  if (direct && typeof direct === "object" && !Array.isArray(direct)) {
    return direct as DraftDoneBar;
  }
  const live = draft?._live_apply;
  if (live && typeof live === "object" && !Array.isArray(live)) {
    const bar = (live as { done_bar?: unknown }).done_bar;
    if (bar && typeof bar === "object" && !Array.isArray(bar)) {
      return bar as DraftDoneBar;
    }
  }
  return undefined;
}

export function goLiveReadyFromDraft(
  draft: Record<string, unknown> | null | undefined,
): boolean {
  if (draft?._go_live_ready) return true;
  const live = draft?._live_apply;
  if (live && typeof live === "object" && !Array.isArray(live)) {
    const rec = live as { go_live_ready?: boolean; done_bar?: DraftDoneBar };
    if (rec.go_live_ready) return true;
    if (rec.done_bar?.go_live_ready) return true;
  }
  return Boolean(doneBarFromDraft(draft)?.go_live_ready);
}

export function scorecardHeadline(opts: {
  score?: number;
  stockReuse?: boolean;
  validatorsGreen?: boolean;
  goLiveReady?: boolean;
  certTier?: string;
}): string {
  const cert = opts.certTier ? ` · Cert: ${opts.certTier}` : "";
  if (typeof opts.score !== "number") return opts.stockReuse ? "Stock coverage" : "Scorecard";
  if (opts.stockReuse) {
    return `Stock coverage — empty ModuleSpec (hygiene ${opts.score.toFixed(1)}/10)${cert}`;
  }
  return `Completeness: ${opts.score.toFixed(1)}/10${
    opts.validatorsGreen ? " · validators green" : ""
  }${opts.goLiveReady ? " · sandbox proven" : ""}${cert}`;
}

export function scorecardBodyCopy(opts: {
  stockReuse?: boolean;
  certShipReady?: boolean;
  goLiveReady?: boolean;
  score?: number;
  hasFindings?: boolean;
}): string | null {
  if (opts.hasFindings) return null;
  if (opts.stockReuse) {
    return "Empty spec is correct. Open Job Autopilot for sandbox install and quote→invoice RPC smoke. Completeness ≠ Cert ≠ Autopilot. Promote stays human.";
  }
  if (opts.certShipReady && opts.goLiveReady) {
    return "Sandbox proven + Certification Production/Gold — ready for human promote.";
  }
  if (opts.certShipReady) {
    return "Certification Production/Gold — review before promote.";
  }
  if (typeof opts.score === "number" && opts.score >= 9.5 && !opts.certShipReady) {
    return "High completeness — not shippable until Certification ≥ Production.";
  }
  return "No major findings — ready for review.";
}

export function createDraftHint(opts: {
  hasDraft?: boolean;
  promptLength: number;
  needsConnectReview?: boolean;
  connectReady?: boolean;
  overlapPending?: boolean;
  isFullAppGrain?: boolean;
}): string {
  if (opts.hasDraft) {
    return "The JSON is the ModuleSpec. Apply to Odoo writes models, forms, and the menu tree. Open ModuleSpec or View Designer to edit.";
  }
  if (opts.promptLength < 3) {
    return "Type what you need (a field, a feature, or a full app), then click Create draft.";
  }
  if (opts.needsConnectReview && !opts.connectReady) {
    return "Component / field pack: click Review connect points, approve the host model, then Create draft.";
  }
  if (opts.overlapPending) {
    return "Resolve overlap findings above (Use, Extend, or Build anyway), then Create draft.";
  }
  if (opts.isFullAppGrain) {
    return "Full app detected — click Create draft. Stock first; custom models only for the residual. Nothing touches Odoo until Apply.";
  }
  return "Click Create draft — we implement on the host app (inherit + fields + view), not a second ERP.";
}
