"use client";

import { cn } from "@/lib/cn";
import {
  JOB_AUTOPILOT_STAGES,
  jobAutopilotJourneyHint,
  type JobAutopilotJourneyState,
} from "@/lib/job-autopilot-journey";

type JobAutopilotStageRailProps = {
  journey: JobAutopilotJourneyState;
};

export function JobAutopilotStageRail({ journey }: JobAutopilotStageRailProps) {
  const currentIndex = JOB_AUTOPILOT_STAGES.findIndex((row) => row.id === journey.id);
  return (
    <nav
      className="studio-stage-rail"
      aria-label="Job Autopilot stages"
      data-testid="job-autopilot-stage-rail"
    >
      <ol className="studio-stage-list" data-testid="job-autopilot-steps">
        {JOB_AUTOPILOT_STAGES.map((stage, index) => {
          const done = index < currentIndex || (journey.promoteReady && stage.id === "promote");
          const current = stage.id === journey.id;
          return (
            <li
              key={stage.id}
              className={cn(
                "studio-stage-item",
                done && "is-done",
                current && "is-current",
                journey.failed && current && "is-failed",
              )}
              data-stage={stage.id}
              aria-current={current ? "step" : undefined}
            >
              <span className="studio-stage-index" aria-hidden>
                {index + 1}
              </span>
              <span className="studio-stage-label">{stage.label}</span>
            </li>
          );
        })}
      </ol>
      <p className="studio-stage-hint" data-testid="job-autopilot-stage-hint">
        {jobAutopilotJourneyHint(journey)}
      </p>
    </nav>
  );
}
