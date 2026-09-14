"use client";

import { Callout } from "@/components/ui/Callout";
import { Button } from "@/components/ui/Button";
import { SCORE_BARS } from "@/lib/copy-guide";
import {
  scorecardBodyCopy,
  scorecardHeadline,
  type DraftCertification,
  type DraftDoneBar,
  type DraftScorecard,
} from "@/lib/draft-studio-journey";
import type { ExpertDraftReviewResponse } from "@/lib/api";

type DraftStudioScorecardProps = {
  scorecard?: DraftScorecard;
  certification?: DraftCertification;
  certTierDisplay?: string;
  certShipReady: boolean;
  doneBar?: DraftDoneBar;
  goLiveReady: boolean;
  stockReuse: boolean;
  isComponent: boolean;
  refuseClone: boolean;
  aiBusy: boolean;
  hasDraft: boolean;
  expertHint: string;
  eliteBusy: boolean;
  eliteLintOk: boolean | null;
  eliteLintNote: string | null;
  eliteValidationId: string | null;
  eliteZipBase64: string | null;
  eliteNote: string | null;
  expertReviewNote: string | null;
  expertReviewFindings: ExpertDraftReviewResponse["findings"];
  finisherComplete: boolean;
  draftSummary?: string;
  onExpertFix: () => void;
  onLint: () => void;
  onValidate: () => void;
  onPromote: () => void;
  onDownloadValidatedZip: () => void;
  onAskExpert: () => void;
};

export function DraftStudioScorecard({
  scorecard,
  certification,
  certTierDisplay,
  certShipReady,
  doneBar,
  goLiveReady,
  stockReuse,
  isComponent,
  refuseClone,
  aiBusy,
  hasDraft,
  expertHint,
  eliteBusy,
  eliteLintOk,
  eliteLintNote,
  eliteValidationId,
  eliteZipBase64,
  eliteNote,
  expertReviewNote,
  expertReviewFindings,
  finisherComplete,
  onExpertFix,
  onLint,
  onValidate,
  onPromote,
  onDownloadValidatedZip,
  onAskExpert,
}: DraftStudioScorecardProps) {
  const draftScore = scorecard?.score_0_10;
  const scoreDimensions = scorecard?.dimensions;
  const validatorsGreen = scorecard?.validators?.all_green === true;
  const findings = Array.isArray(scorecard?.findings) ? scorecard.findings : [];
  if (typeof draftScore !== "number") return null;

  const body = scorecardBodyCopy({
    stockReuse,
    certShipReady,
    goLiveReady,
    score: draftScore,
    hasFindings: findings.length > 0,
  });

  return (
    <Callout
      variant="info"
      title={scorecardHeadline({
        score: draftScore,
        stockReuse,
        validatorsGreen,
        goLiveReady,
        certTier: certTierDisplay,
      })}
      testId="draft-scorecard-chip"
    >
      {scoreDimensions ? (
        <p className="text-xs text-muted">
          Domain {scoreDimensions.domain_fit?.toFixed(1) ?? "—"} · Structure{" "}
          {scoreDimensions.structure?.toFixed(1) ?? "—"} · Semantics{" "}
          {scoreDimensions.semantics?.toFixed(1) ?? "—"} · UX{" "}
          {scoreDimensions.ux?.toFixed(1) ?? "—"} · Hygiene{" "}
          {scoreDimensions.hygiene?.toFixed(1) ?? "—"}
        </p>
      ) : null}
      {certification ? (
        <p className="mt-1 text-xs text-muted" data-testid="certification-chip">
          Certification {certTierDisplay ?? "—"} — Quality{" "}
          {typeof certification.quality === "number" ? certification.quality.toFixed(0) : "—"}
          · Evidence{" "}
          {typeof certification.evidence === "number" ? certification.evidence.toFixed(0) : "—"}
          · Risk {typeof certification.risk === "number" ? certification.risk.toFixed(0) : "—"}
          {!certShipReady
            ? stockReuse
              ? " — empty-spec hygiene is not go-live; Autopilot smoke is the done-bar"
              : " — completeness 10.0 is not go-live until Cert ≥ Production (and Option A smoke if pending)"
            : " — promote stays human; Autopilot smoke is a separate job scorecard"}
        </p>
      ) : null}
      {doneBar?.mode ? (
        <p className="mt-1 text-xs text-muted" data-testid="done-bar-chip">
          Done-bar: {doneBar.mode}
          {doneBar.next_step ? ` — ${doneBar.next_step}` : ""}
        </p>
      ) : null}
      <ul className="mt-2 list-disc space-y-1 pl-5 text-[11px] text-muted" data-testid="score-bars-legend">
        <li>{SCORE_BARS.completeness}</li>
        <li>{SCORE_BARS.certification}</li>
        <li>{SCORE_BARS.autopilot}</li>
      </ul>
      {findings.length > 0 ? (
        <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
          {findings.slice(0, 6).map((f, i) => (
            <li key={`${f.element}-${i}`}>
              {f.dimension ? <span className="text-muted">{f.dimension}: </span> : null}
              {f.element}: {f.detail}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm">{body}</p>
      )}
      <Button
        type="button"
        variant="secondary"
        size="sm"
        className="mt-2"
        disabled={aiBusy || !hasDraft || refuseClone}
        data-testid="expert-review-fix"
        onClick={onExpertFix}
      >
        Ask the Expert to review and fix
      </Button>
      <p className="mt-1 text-[11px] text-muted" data-testid="expert-review-fix-hint">
        {expertHint}
      </p>
      {!stockReuse && !isComponent && draftScore >= 9 ? (
        <div className="mt-3 space-y-2" data-testid="elite-promote-workflow">
          <p className="text-xs text-muted">
            Optional installable module (Python, mail, cron, tests). Not required to
            view the app — Apply to Odoo / Open ModuleSpec already generate the UI.
            Use this path when you want a zip, sandbox install, then promote.
          </p>
          {eliteLintNote ? (
            <p
              className={`text-xs ${eliteLintOk === false ? "text-warning" : "text-muted"}`}
              data-testid="elite-lint-note"
            >
              {eliteLintNote}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={!hasDraft || eliteBusy}
              onClick={onLint}
            >
              Lint Python blocks
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              loading={eliteBusy}
              disabled={!hasDraft || eliteBusy || !finisherComplete}
              data-testid="elite-validate-module"
              onClick={onValidate}
            >
              Validate module (sandbox)
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              disabled={!eliteValidationId || !eliteZipBase64 || eliteBusy}
              data-testid="elite-promote-module"
              onClick={onPromote}
            >
              Promote module
            </Button>
            {eliteZipBase64 ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                data-testid="elite-download-zip"
                onClick={onDownloadValidatedZip}
              >
                Download validated zip
              </Button>
            ) : null}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              data-testid="expert-ask-draft"
              onClick={onAskExpert}
            >
              Ask Expert about draft
            </Button>
          </div>
        </div>
      ) : null}
      {eliteNote ? <p className="mt-2 text-sm text-muted">{eliteNote}</p> : null}
      {expertReviewNote ? <p className="mt-2 text-sm text-muted">{expertReviewNote}</p> : null}
      {expertReviewFindings.some((f) => f.narrative_paragraph) ? (
        <div className="mt-3 space-y-3" data-testid="expert-review-narratives">
          {expertReviewFindings
            .filter((f) => f.narrative_paragraph)
            .slice(0, 5)
            .map((f) => (
              <div key={f.priority} className="rounded-md border border-border-subtle p-2">
                <p className="text-xs font-medium text-ink">{f.summary}</p>
                <p className="mt-1 text-sm text-muted">{f.narrative_paragraph}</p>
              </div>
            ))}
        </div>
      ) : null}
    </Callout>
  );
}
