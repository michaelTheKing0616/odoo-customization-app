"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { SCORE_BARS } from "@/lib/copy-guide";
import {
  formatHygieneScore,
  scorecardBodyCopy,
  scorecardHeadline,
  type DraftCertification,
  type DraftDoneBar,
  type DraftScorecard,
} from "@/lib/draft-studio-journey";
import type { ExpertDraftReviewResponse } from "@/lib/api";
import { WIZARD_ONLINE_PROMOTE_REASON } from "@/lib/wizard-ui";

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
  /** Odoo Online cannot take a custom Python module: Publish stays off with a reason. */
  isOdooOnline?: boolean;
  /** Where the Autopilot bar is actually measured. */
  jobAutopilotHref?: string;
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
  isOdooOnline = false,
  jobAutopilotHref,
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

  const completenessTitle = stockReuse
    ? scorecardHeadline({ score: draftScore, stockReuse: true })
    : `Completeness: ${formatHygieneScore(draftScore)}/10`;
  const certTier = certTierDisplay || certification?.tier;
  const promoteReason = isOdooOnline
    ? WIZARD_ONLINE_PROMOTE_REASON
    : !eliteValidationId || !eliteZipBase64
      ? "Validate the module in a sandbox first."
      : null;

  return (
    <section
      className="draft-studio-diagnosis"
      data-testid="draft-scorecard-chip"
      aria-labelledby="draft-scorecard-title"
    >
      <header className="draft-studio-diagnosis-header">
        <h3 id="draft-scorecard-title" className="draft-studio-diagnosis-title">
          Scorecard
        </h3>
        <p className="draft-studio-diagnosis-lede">
          Three separate bars. A high score on one never implies another.
        </p>
      </header>
      <div className="draft-studio-diagnosis-body">
        <ul className="draft-studio-score-bars" data-testid="score-bars-legend">
          <li data-bar="completeness">
            <p className="draft-studio-score-bar-title">{completenessTitle}</p>
            {validatorsGreen ? (
              <p className="draft-studio-score-bar-flags">
                <span>Validators green</span>
              </p>
            ) : null}
            {scoreDimensions ? (
              <p className="draft-studio-diagnosis-dims">
                Domain{" "}
                {typeof scoreDimensions.domain_fit === "number"
                  ? formatHygieneScore(scoreDimensions.domain_fit)
                  : "–"}{" "}
                · Structure{" "}
                {typeof scoreDimensions.structure === "number"
                  ? formatHygieneScore(scoreDimensions.structure)
                  : "–"}{" "}
                · Semantics{" "}
                {typeof scoreDimensions.semantics === "number"
                  ? formatHygieneScore(scoreDimensions.semantics)
                  : "–"}{" "}
                · UX{" "}
                {typeof scoreDimensions.ux === "number"
                  ? formatHygieneScore(scoreDimensions.ux)
                  : "–"}{" "}
                · Hygiene{" "}
                {typeof scoreDimensions.hygiene === "number"
                  ? formatHygieneScore(scoreDimensions.hygiene)
                  : "–"}
              </p>
            ) : null}
            <p className="draft-studio-score-bar-copy">{SCORE_BARS.completeness}</p>
            {findings.length > 0 ? (
              <ul className="draft-studio-findings" data-testid="draft-scorecard-findings">
                {findings.slice(0, 6).map((f, i) => (
                  <li key={`${f.element}-${i}`}>
                    {f.dimension ? <span className="text-muted">{f.dimension}: </span> : null}
                    {f.element}: {f.detail}
                  </li>
                ))}
              </ul>
            ) : body ? (
              <p className="draft-studio-score-bar-body">{body}</p>
            ) : null}
          </li>
          <li data-bar="certification">
            <p className="draft-studio-score-bar-title">
              Certification: {certTier ?? "not scored yet"}
            </p>
            {goLiveReady ? (
              <p className="draft-studio-score-bar-flags">
                <span>Sandbox proven</span>
              </p>
            ) : null}
            {certification ? (
              <p className="draft-studio-diagnosis-dims" data-testid="certification-chip">
                Quality{" "}
                {typeof certification.quality === "number" ? certification.quality.toFixed(0) : "–"}
                {" · "}Evidence{" "}
                {typeof certification.evidence === "number" ? certification.evidence.toFixed(0) : "–"}
                {" · "}Risk{" "}
                {typeof certification.risk === "number" ? certification.risk.toFixed(0) : "–"}
                {!certShipReady
                  ? stockReuse
                    ? ". An empty draft's structure score is not go-live; an Autopilot smoke test is the done bar"
                    : ". A complete draft is not go-live until quality checks pass (and a custom-code smoke test if needed)"
                  : ". Publishing stays a step you confirm; Autopilot smoke is a separate job scorecard"}
              </p>
            ) : null}
            <p className="draft-studio-score-bar-copy">{SCORE_BARS.certification}</p>
          </li>
          <li data-bar="autopilot">
            <p className="draft-studio-score-bar-title">
              Autopilot: measured on Job Autopilot
            </p>
            {doneBar?.mode ? (
              <p className="draft-studio-diagnosis-dims" data-testid="done-bar-chip">
                Done-bar: {doneBar.mode}
                {doneBar.next_step ? `: ${doneBar.next_step}` : ""}
              </p>
            ) : null}
            <p className="draft-studio-score-bar-copy">{SCORE_BARS.autopilot}</p>
            {jobAutopilotHref ? (
              <Link
                href={jobAutopilotHref}
                className="draft-studio-score-bar-link"
                data-testid="scorecard-job-autopilot-link"
              >
                Open Job Autopilot
              </Link>
            ) : null}
          </li>
        </ul>
        <div className="draft-studio-diagnosis-expert">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            disabled={aiBusy || !hasDraft || refuseClone}
            data-testid="expert-review-fix"
            onClick={onExpertFix}
          >
            Ask the Expert to review and fix
          </Button>
          {expertHint ? (
            <p className="draft-studio-score-bar-copy" data-testid="expert-review-fix-hint">
              {expertHint}
            </p>
          ) : null}
        </div>
        {!stockReuse && !isComponent && draftScore >= 9 ? (
          <section
            className="draft-studio-elite"
            data-testid="elite-promote-workflow"
            aria-labelledby="elite-promote-title"
          >
            <h4 id="elite-promote-title" className="draft-studio-elite-title">
              Installable module (optional)
            </h4>
            <p className="draft-studio-score-bar-copy">
              Python, mail, cron, and tests in a zip. Not required to view the app: Apply to
              Odoo and Open ModuleSpec already generate the UI. Use this path for a zip,
              sandbox install, then a human Promote.
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
                variant="secondary"
                size="sm"
                disabled={!eliteValidationId || !eliteZipBase64 || eliteBusy || isOdooOnline}
                title={promoteReason ?? "Installs the validated module on this connection after you confirm"}
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
            {isOdooOnline ? (
              <p className="draft-studio-score-bar-copy" data-testid="elite-promote-online-reason">
                {WIZARD_ONLINE_PROMOTE_REASON}
              </p>
            ) : null}
          </section>
        ) : null}
        {eliteNote ? <p className="text-sm text-muted">{eliteNote}</p> : null}
        {expertReviewNote ? <p className="text-sm text-muted">{expertReviewNote}</p> : null}
        {expertReviewFindings.some((f) => f.narrative_paragraph) ? (
          <div className="space-y-3" data-testid="expert-review-narratives">
            {expertReviewFindings
              .filter((f) => f.narrative_paragraph)
              .slice(0, 5)
              .map((f) => (
                <div key={f.priority} className="draft-studio-narrative">
                  <p className="text-xs font-medium text-ink">{f.summary}</p>
                  <p className="mt-1 text-sm text-muted">{f.narrative_paragraph}</p>
                </div>
              ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}
