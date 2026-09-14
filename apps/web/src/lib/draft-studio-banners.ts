/** Wizard warning copy derived from draft JSON — never invent gaps from `ready: false`. */

import { SCORE_BARS } from "./copy-guide";
import {
  draftFinisherComplete,
  isOptionAAuthoredDraft,
  isRefuseCloneDraft,
  isStockReuseDraft,
  optionAAuthoringPassed,
} from "./draft-form-preview";

export type DraftBanner = {
  title: string;
  body: string;
  testId: string;
};

type LiveFinding = { detail?: string; element?: string };
type ScoreFinding = { dimension?: string; element?: string; detail?: string };

function asRecord(draft: unknown): Record<string, unknown> | null {
  if (!draft || typeof draft !== "object" || Array.isArray(draft)) return null;
  return draft as Record<string, unknown>;
}

function liveBlock(draft: Record<string, unknown> | null) {
  const live = draft?._live_apply;
  if (!live || typeof live !== "object" || Array.isArray(live)) return null;
  return live as { ready?: boolean; findings?: LiveFinding[] };
}

function quotedLiveFindings(draft: Record<string, unknown> | null): string[] {
  const rows = liveBlock(draft)?.findings;
  if (!Array.isArray(rows)) return [];
  return rows
    .map((row) => String(row?.detail || "").trim())
    .filter(Boolean);
}

function scorecardFindings(draft: Record<string, unknown> | null): ScoreFinding[] {
  const card = draft?._scorecard;
  if (!card || typeof card !== "object" || Array.isArray(card)) return [];
  const rows = (card as { findings?: ScoreFinding[] }).findings;
  return Array.isArray(rows) ? rows.filter((row) => row && String(row.detail || "").trim()) : [];
}

/** Expert closer is for JSON hygiene only — not Cert, not Autopilot, not empty stock_reuse. */
export function expertShouldRepair(draft: unknown): boolean {
  const rec = asRecord(draft);
  if (!rec) return false;
  if (isStockReuseDraft(rec) || isRefuseCloneDraft(rec)) return false;
  if (scorecardFindings(rec).length > 0) return true;
  return quotedLiveFindings(rec).length > 0;
}

export function expertCloserHint(draft: unknown): string {
  const rec = asRecord(draft);
  if (isStockReuseDraft(rec)) {
    return "Expert closer repairs JSON hygiene. It does not install Community apps or run Autopilot smoke. Use Job Autopilot as the done-bar.";
  }
  if (isRefuseCloneDraft(rec)) {
    return "This request was refused — Expert will not generate a clone.";
  }
  if (rec?._component) {
    return "This is inherit-and-wire on a stock form. Next step is Apply — Expert closer is for full-app drafts with JSON gaps.";
  }
  if (isOptionAAuthoredDraft(rec) && !optionAAuthoringPassed(rec)) {
    return "LLM-authored Python/QWeb is gated. Expert closer does not unlock zip — fix authoring findings, then sandbox-prove. Promote stays human.";
  }
  if (rec?._capability_primary_option_a) {
    return "Option A primary: score stays capped (~7) until Sandbox install & smoke. Expert closer does not raise Certification.";
  }
  if (!expertShouldRepair(rec)) {
    return "No JSON gaps to repair. Expert will leave this spec unchanged.";
  }
  return SCORE_BARS.expertFix;
}

/**
 * Live-apply warning only when `_live_apply.findings` has real rows.
 * `ready: false` with empty findings is intentional (stock_reuse) — not missing dates.
 */
export function liveApplyGapBanner(draft: unknown): DraftBanner | null {
  const rec = asRecord(draft);
  if (!rec) return null;
  if (isStockReuseDraft(rec) || isRefuseCloneDraft(rec)) return null;
  const live = liveBlock(rec);
  if (!live || live.ready !== false) return null;
  const details = quotedLiveFindings(rec);
  if (details.length === 0) return null;
  const quoted = details.slice(0, 4).join(" ");
  return {
    title: "Not live-apply ready",
    body: `This draft still has live-apply gaps: ${quoted} Click Expert review and fix, then Apply.`,
    testId: "live-apply-not-ready",
  };
}

export function displayedCertificationTier(draft: unknown): string | undefined {
  const rec = asRecord(draft);
  if (!rec) return undefined;
  const cert = rec._certification as { tier?: string } | undefined;
  const live = rec._live_apply as { certification_tier?: string } | undefined;
  const stockReuse = isStockReuseDraft(rec);
  const rank: Record<string, number> = {
    Reject: 0,
    ReviewRequired: 1,
    Production: 2,
    Gold: 3,
  };
  const tier = cert?.tier;
  if (stockReuse && (tier === "Production" || tier === "Gold")) {
    return "ReviewRequired";
  }
  const liveTier = live?.certification_tier;
  if (
    liveTier &&
    tier &&
    (rank[liveTier] ?? 99) < (rank[tier] ?? 99)
  ) {
    return liveTier;
  }
  if (liveTier === "ReviewRequired" && (tier === "Production" || tier === "Gold")) {
    return "ReviewRequired";
  }
  return tier;
}

export function unfinishedDraftBanner(
  draft: unknown,
  opts?: { generating?: boolean },
): DraftBanner | null {
  const rec = asRecord(draft);
  if (!rec) return null;
  if (draftFinisherComplete(rec)) return null;
  const generating = Boolean(opts?.generating);
  return {
    title: generating ? "Still generating" : "Unfinished draft",
    body: generating
      ? "This is a live preview. Wait for the quality score before applying."
      : "This draft is missing a quality score. Click Create draft again — do not Apply yet.",
    testId: "draft-finisher-incomplete",
  };
}
