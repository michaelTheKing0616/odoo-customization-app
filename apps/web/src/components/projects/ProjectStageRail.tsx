"use client";

import { cn } from "@/lib/cn";
import {
  PROJECTS_STAGES,
  projectsJourneyHint,
  type ProjectsJourneyState,
} from "@/lib/projects-journey";

type ProjectStageRailProps = {
  journey: ProjectsJourneyState;
};

export function ProjectStageRail({ journey }: ProjectStageRailProps) {
  const currentIndex = PROJECTS_STAGES.findIndex((row) => row.id === journey.id);
  return (
    <nav
      className="studio-stage-rail"
      aria-label="Projects stages"
      data-testid="projects-stage-rail"
    >
      <ol className="studio-stage-list" data-testid="projects-steps">
        {PROJECTS_STAGES.map((stage, index) => {
          const done = index < currentIndex || (journey.applied && stage.id === "apply");
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
      <p className="studio-stage-hint" data-testid="projects-stage-hint">
        {projectsJourneyHint(journey)}
      </p>
    </nav>
  );
}
