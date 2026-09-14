"use client";

import { InfinityLoop } from "@/components/loading-ui/infinity-loop";
import { jobProgressHonestyLine } from "@/lib/job-autopilot-resume";
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
      <p className="studio-progress-detail" data-testid="job-autopilot-progress-honesty">
        {jobProgressHonestyLine()}
      </p>
      <div className="progress-bar-track" aria-hidden>
        <div className="progress-bar-fill" />
      </div>
      <JobAutopilotRunLedger stages={stages} currentStep={currentStep} compact />
    </div>
  );
}
