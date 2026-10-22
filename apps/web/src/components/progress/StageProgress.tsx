"use client";

import { useEffect, useMemo, useState } from "react";
import { stageFriendlyLabel } from "@/lib/progress/stage-labels";
import { useStageEvents } from "@/lib/progress/use-stage-events";

export type StageProgressProps = {
  runId: string | null | undefined;
  active: boolean;
  fallbackLabel?: string;
  onContinue?: () => void;
  onStop?: () => void;
  className?: string;
};

export function StageProgress({
  runId,
  active,
  fallbackLabel = "Working…",
  onContinue,
  onStop,
  className,
}: StageProgressProps) {
  const { events, latest, error } = useStageEvents(runId, active);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [toolLimitOpen, setToolLimitOpen] = useState(false);

  useEffect(() => {
    if (latest?.stage === "tool_call_limit") {
      setToolLimitOpen(true);
    }
  }, [latest?.stage]);

  const label = useMemo(() => {
    // No stage event yet: show the caller's job label, not a generic "Working…".
    if (!latest?.stage) return fallbackLabel;
    return stageFriendlyLabel(latest.stage);
  }, [fallbackLabel, latest?.stage]);

  if (!active) return null;

  const detailLines = events
    .filter((e) => e.detail?.trim())
    .map((e) => `${e.stage}: ${e.detail}`);

  return (
    <div
      className={className ?? "stage-progress"}
      data-testid="stage-progress"
      role="status"
      aria-live="polite"
    >
      <p className="stage-progress-label" data-testid="stage-progress-label">
        {label}
      </p>
      <div className="progress-bar-track mt-2" aria-hidden>
        <div className="progress-bar-fill" />
      </div>
      {detailLines.length || error ? (
        <div className="mt-2">
          <button
            type="button"
            className="text-xs text-muted underline-offset-2 hover:underline"
            aria-expanded={detailsOpen}
            onClick={() => setDetailsOpen((v) => !v)}
            data-testid="stage-progress-details-toggle"
          >
            {detailsOpen ? "Hide details" : "Show details"}
          </button>
          {detailsOpen ? (
            <div
              className="mt-2 rounded-md border border-border-subtle bg-surface-muted p-2 font-mono text-[11px] text-muted"
              data-testid="stage-progress-details"
            >
              {error ? <p className="text-danger">{error}</p> : null}
              {detailLines.map((line, idx) => (
                <p key={`${line}-${idx}`}>{line}</p>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
      {toolLimitOpen ? (
        <div
          className="mt-3 rounded-md border border-warning/40 bg-warning-subtle p-3 text-sm"
          data-testid="tool-call-limit-prompt"
        >
          <p className="font-medium text-ink">Continue or stop?</p>
          <p className="mt-1 text-xs text-muted">
            This run hit the tool-call limit. It will not continue until you choose.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              className="btn btn-brand btn-sm"
              data-testid="tool-call-limit-continue"
              onClick={() => {
                setToolLimitOpen(false);
                onContinue?.();
              }}
            >
              Continue
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              data-testid="tool-call-limit-stop"
              onClick={() => {
                setToolLimitOpen(false);
                onStop?.();
              }}
            >
              Stop
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
