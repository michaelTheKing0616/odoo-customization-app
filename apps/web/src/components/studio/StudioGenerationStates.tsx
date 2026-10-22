"use client";

import { StageProgress } from "@/components/progress/StageProgress";
import { StudioBusyLabel } from "./StudioBusyLabel";

type StudioGeneratingCanvasProps = {
  runId: string | null;
  /** Stage label from the job row when stage events have not arrived yet. */
  fallbackLabel: string;
};

/** Generate in flight: paper-on-desk skeleton plus stage-accurate progress (no fake %). */
export function StudioGeneratingCanvas({ runId, fallbackLabel }: StudioGeneratingCanvasProps) {
  return (
    <div className="studio-canvas-progress" data-testid="studio-generating" aria-busy="true">
      <div className="studio-canvas-ghost" aria-hidden>
        <div className="studio-canvas-ghost-desk">
          <div className="studio-canvas-ghost-page">
            <div className="studio-canvas-ghost-bar" />
            <div className="studio-canvas-ghost-sheet">
              <div className="studio-canvas-ghost-row" />
              <div className="studio-canvas-ghost-row is-short" />
              <div className="studio-canvas-ghost-row" />
              <div className="studio-canvas-ghost-row is-mid" />
              <div className="studio-canvas-ghost-row is-short" />
              <div className="studio-canvas-ghost-row" />
            </div>
          </div>
        </div>
      </div>
      <div className="studio-canvas-progress-body">
        <StageProgress runId={runId} active fallbackLabel={fallbackLabel} />
        <p className="studio-canvas-progress-note">
          The form preview replaces this placeholder when the draft is ready.
        </p>
      </div>
    </div>
  );
}

type StudioGenerationFailedProps = {
  message: string | null | undefined;
  retrying: boolean;
  onRetry: () => void;
  onStartOver: () => void;
};

/** Generate failed: what happened, then the two ways forward (Stitch-grade recovery). */
export function StudioGenerationFailed({
  message,
  retrying,
  onRetry,
  onStartOver,
}: StudioGenerationFailedProps) {
  return (
    <section
      className="studio-generation-failed card"
      data-testid="studio-generation-failed"
      aria-labelledby="studio-generation-failed-title"
    >
      <h2 id="studio-generation-failed-title" className="studio-generation-failed-title">
        Generation didn&apos;t finish
      </h2>
      <p className="studio-generation-failed-body">
        {message || "The draft job stopped before it produced a form."}
      </p>
      <p className="studio-generation-failed-hint">
        Generate again reuses the same brief and diagnosis. Start over clears this session.
      </p>
      <div className="studio-generation-failed-actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={retrying}
          onClick={onRetry}
        >
          {retrying ? <StudioBusyLabel>Generating…</StudioBusyLabel> : "Generate again"}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onStartOver}>
          Start over
        </button>
      </div>
    </section>
  );
}
