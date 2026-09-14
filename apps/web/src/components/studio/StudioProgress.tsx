"use client";

import { InfinityLoop } from "@/components/loading-ui/infinity-loop";

type StudioProgressProps = {
  label: string;
  detail?: string | null;
};

export function StudioProgress({ label, detail }: StudioProgressProps) {
  return (
    <div className="studio-progress-screen" data-testid="studio-progress">
      <InfinityLoop aria-hidden />
      <p className="studio-progress-label">{label}</p>
      {detail ? <p className="studio-progress-detail">{detail}</p> : null}
      <div className="progress-bar-track" aria-hidden>
        <div className="progress-bar-fill" />
      </div>
    </div>
  );
}
