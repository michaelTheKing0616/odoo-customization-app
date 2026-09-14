"use client";

import { Badge } from "@/components/ui/Badge";
import { Callout } from "@/components/ui/Callout";
import { SCORE_BARS } from "@/lib/copy-guide";
import type { JobProbeResult, JobScorecard } from "@/lib/api";
import {
  jobScorecardBody,
  jobScorecardHeadline,
} from "@/lib/job-autopilot-journey";

type Smoke = {
  ok: boolean;
  steps: JobProbeResult[];
  named_process?: string | null;
  message: string;
};

type JobAutopilotScorecardProps = {
  scorecard?: JobScorecard | null;
  smoke?: Smoke | null;
  promoteReady?: boolean;
  stockOnly?: boolean;
  retryCount?: number;
};

function meterWidth(value: number): string {
  return `${Math.max(0, Math.min(100, (value / 10) * 100))}%`;
}

export function JobAutopilotScorecard({
  scorecard,
  smoke,
  promoteReady,
  stockOnly,
  retryCount,
}: JobAutopilotScorecardProps) {
  if (!scorecard && !smoke) return null;
  const findings = scorecard?.findings ?? [];
  const body = jobScorecardBody({
    smokeOk: smoke?.ok ?? null,
    promoteReady,
    stockOnly,
    hasFindings: findings.length > 0,
  });
  const meters = scorecard
    ? [
        { id: "stack", label: "Stack fit", value: scorecard.stack_fit },
        { id: "coverage", label: "Stock coverage", value: scorecard.stock_coverage },
        { id: "data", label: "Data load", value: scorecard.data_load },
        { id: "smoke", label: "Process smoke", value: scorecard.process_smoke },
      ]
    : [];

  return (
    <Callout
      variant={smoke?.ok === false ? "warning" : "info"}
      title={jobScorecardHeadline({
        overall: scorecard?.overall,
        smokeOk: smoke?.ok ?? null,
        promoteReady,
      })}
      testId="job-scorecard-chip"
    >
      {scorecard?.modulespec_completeness_note ? (
        <p className="text-xs text-muted">{scorecard.modulespec_completeness_note}</p>
      ) : null}
      {scorecard ? (
        <div className="job-score-overall mt-3" data-testid="job-score-overall">
          <span className="job-score-overall-value">{scorecard.overall.toFixed(1)}</span>
          <span className="text-xs text-muted">/10 implementation-job — not Completeness, not Cert</span>
        </div>
      ) : null}
      {meters.length ? (
        <div className="job-score-grid mt-3" data-testid="job-score-meters">
          {meters.map((row) => (
            <div key={row.id} className="job-score-meter">
              <div className="job-score-meter-label">
                <span>{row.label}</span>
                <span>{row.value.toFixed(1)}</span>
              </div>
              <div className="job-score-meter-track" aria-hidden>
                <div className="job-score-meter-fill" style={{ width: meterWidth(row.value) }} />
              </div>
            </div>
          ))}
        </div>
      ) : null}
      {typeof retryCount === "number" && retryCount > 0 ? (
        <p className="mt-2 text-xs text-muted">Retries: {retryCount}</p>
      ) : null}
      <ul className="mt-3 list-disc space-y-1 pl-5 text-[11px] text-muted" data-testid="job-scorecard-legend">
        <li>{SCORE_BARS.completeness}</li>
        <li>{SCORE_BARS.certification}</li>
        <li>{SCORE_BARS.autopilot}</li>
      </ul>
      {findings.length ? (
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
          {findings.slice(0, 8).map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      ) : body ? (
        <p className="mt-2 text-sm">{body}</p>
      ) : null}
      {smoke ? (
        <div className="job-smoke-strip mt-4" data-testid="job-smoke-strip">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={smoke.ok ? "success" : "danger"}>
              {smoke.ok ? "Smoke passed" : "Smoke failed"}
            </Badge>
            {smoke.named_process ? (
              <span className="text-xs text-muted">{smoke.named_process}</span>
            ) : null}
          </div>
          <p className="mt-2 text-sm">{smoke.message}</p>
          <ol className="job-smoke-steps mt-2">
            {smoke.steps.map((step) => (
              <li key={step.name} className="job-smoke-step">
                <Badge variant={step.ok ? "success" : "danger"}>{step.ok ? "ok" : "fail"}</Badge>
                <span>
                  <span className="font-medium text-ink">{step.name}</span>
                  <span className="mt-0.5 block text-xs text-muted">{step.detail}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </Callout>
  );
}
