"use client";

import { InfinityLoop } from "@/components/loading-ui/infinity-loop";
import { JobAutopilotRunLedger } from "./JobAutopilotRunLedger";

type JobAutopilotProgressProps = {
  label: string;
  stages?: string[];
  currentStep?: string | null;
};

export function JobAutopilotProgress({
  label,
  stages,
  currentStep,
}: JobAutopilotProgressProps) {
  return (
    <div className="studio-progress-screen" data-testid="job-autopilot-progress">
      <InfinityLoop aria-hidden />
      <p className="studio-progress-label" data-testid="job-autopilot-progress-label">
        {label}
      </p>
      <p className="studio-progress-detail">
        Completeness ≠ Cert ≠ Autopilot. Promote stays human. You can leave this page —
        the job keeps running.
      </p>
      <div className="progress-bar-track" aria-hidden>
        <div className="progress-bar-fill" />
      </div>
      <JobAutopilotRunLedger stages={stages} currentStep={currentStep} compact />
    </div>
  );
}
