"use client";

import { InfinityLoop } from "@/components/loading-ui/infinity-loop";

type DraftStudioProgressProps = {
  label: string;
};

export function DraftStudioProgress({ label }: DraftStudioProgressProps) {
  return (
    <div
      className="studio-progress-screen draft-studio-progress"
      data-testid="draft-studio-progress"
      role="status"
      aria-live="polite"
    >
      <InfinityLoop aria-hidden />
      <p className="studio-progress-label" data-testid="generation-phase">
        {label}
      </p>
      <p className="studio-progress-detail">
        Nothing writes to Odoo while this runs. You can leave; the job keeps running.
      </p>
      <div className="progress-bar-track" aria-hidden>
        <div className="progress-bar-fill" />
      </div>
    </div>
  );
}
