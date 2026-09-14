"use client";

import { InfinityLoop } from "@/components/loading-ui/infinity-loop";

type DraftStudioProgressProps = {
  label: string;
};

export function DraftStudioProgress({ label }: DraftStudioProgressProps) {
  return (
    <div
      className="studio-progress-screen"
      data-testid="draft-studio-progress"
    >
      <InfinityLoop aria-hidden />
      <p className="studio-progress-label" data-testid="generation-phase">
        {label}
      </p>
      <p className="studio-progress-detail">
        Completeness is not Cert. Promote stays human. You can leave this page — the job keeps running.
      </p>
      <div className="progress-bar-track" aria-hidden>
        <div className="progress-bar-fill" />
      </div>
    </div>
  );
}
