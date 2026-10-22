/** Draft Studio journey stages: chrome only, not the generator. Distinct from App Studio. */

import { actionErrorTitle } from "./action-error-title";

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
    return "Draft did not finish. Retry enrichment, or generate the draft again. Publishing stays a step you confirm.";
  }
  switch (state.id) {
    case "prompt":
      return "Describe a field, a feature, or a full app. Generating the draft builds an app plan. Nothing writes to Odoo yet.";
    case "enrich":
      return "Quality pass is running. Completeness is not Cert. Publishing stays a step you confirm.";
    case "review":
      return "Scorecard is app plan hygiene, not go-live. Apply writes live metadata. Zip, sandbox, then publish.";
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

export const DRAFT_STUDIO_ERROR_STEPS = {
  enrich: "Enrichment failed",
  draft: "Draft failed",
  zip: "Zip export failed",
  sandbox: "Sandbox validate failed",
  repair: "AI repair did not apply",
  promote: "Publish failed",
  apply: "Apply failed",
  scaffold: "Scaffold failed",
} as const;

export type DraftStudioErrorStep = keyof typeof DRAFT_STUDIO_ERROR_STEPS;

export function draftStudioErrorTitle(
  stepOrMessage?: string | null,
  message?: string | null,
): string {
  return actionErrorTitle(
    stepOrMessage,
    DRAFT_STUDIO_ERROR_STEPS,
    "Draft Studio request failed",
    message,
  );
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


/** Present real hygiene scores without fake-decimal theater (7 not 7.0; keep 7.2). */
export function formatHygieneScore(score: number): string {
  const rounded = Math.round(score * 10) / 10;
  if (Math.abs(rounded - Math.round(rounded)) < 0.05) {
    return String(Math.round(rounded));
  }
  return rounded.toFixed(1);
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
    return `Stock coverage: empty app plan (hygiene ${formatHygieneScore(opts.score)}/10)${cert}`;
  }
  return `Completeness: ${formatHygieneScore(opts.score)}/10${
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
    return "Empty spec is correct. Open Job Autopilot for sandbox install and quote→invoice RPC smoke. A complete draft is not the same as certified, and neither means Autopilot-ready. Publishing stays a step you confirm.";
  }
  if (opts.certShipReady && opts.goLiveReady) {
    return "Sandbox proven + Certification Production/Gold. Ready for human promote.";
  }
  if (opts.certShipReady) {
    return "Certification Production/Gold. Review before publish.";
  }
  if (typeof opts.score === "number" && opts.score >= 9.5 && !opts.certShipReady) {
    return "High completeness, not shippable until Certification ≥ Production.";
  }
  return "No major findings. Ready for review.";
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
    return "The JSON is the app plan. Apply to Odoo writes models, forms, and the menu tree. Open app plan or View Designer to edit.";
  }
  if (opts.promptLength < 3) {
    return "Type what you need (a field, a feature, or a full app), then generate the draft.";
  }
  if (opts.needsConnectReview && !opts.connectReady) {
    return "Component or field pack: Review connect points, approve the existing form, then generate the draft.";
  }
  if (opts.overlapPending) {
    return "Resolve overlap findings above (Use, Extend, or Build anyway), then generate the draft.";
  }
  if (opts.isFullAppGrain) {
    return "Full app detected. Stock apps first, custom models only for the residual. Nothing touches Odoo until Apply.";
  }
  return "Ingenium builds on the host app (inherit, fields, view), not a second ERP. Nothing writes to Odoo until Apply.";
}
