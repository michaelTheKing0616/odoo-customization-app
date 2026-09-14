"use client";

import { cn } from "@/lib/cn";
import {
  STUDIO_STAGES,
  studioJourneyHint,
  type StudioJourneyState,
} from "@/lib/studio-journey";

type StudioStageRailProps = {
  journey: StudioJourneyState;
};

export function StudioStageRail({ journey }: StudioStageRailProps) {
  const currentIndex = STUDIO_STAGES.findIndex((row) => row.id === journey.id);
  return (
    <nav
      className="studio-stage-rail"
      aria-label="App Studio stages"
      data-testid="studio-stage-rail"
    >
      <ol className="studio-stage-list">
        {STUDIO_STAGES.map((stage, index) => {
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
      <p className="studio-stage-hint" data-testid="studio-stage-hint">
        {studioJourneyHint(journey)}
      </p>
    </nav>
  );
}
