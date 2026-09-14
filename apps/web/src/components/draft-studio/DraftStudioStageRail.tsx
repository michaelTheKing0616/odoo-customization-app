"use client";

import { cn } from "@/lib/cn";
import {
  DRAFT_STUDIO_STAGES,
  draftStudioJourneyHint,
  type DraftStudioJourneyState,
} from "@/lib/draft-studio-journey";

type DraftStudioStageRailProps = {
  journey: DraftStudioJourneyState;
};

export function DraftStudioStageRail({ journey }: DraftStudioStageRailProps) {
  const currentIndex = DRAFT_STUDIO_STAGES.findIndex((row) => row.id === journey.id);
  return (
    <nav
      className="studio-stage-rail"
      aria-label="Draft Studio stages"
      data-testid="draft-studio-stage-rail"
    >
      <ol className="studio-stage-list" data-testid="draft-studio-steps">
        {DRAFT_STUDIO_STAGES.map((stage, index) => {
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
      <p className="studio-stage-hint" data-testid="draft-studio-stage-hint">
        {draftStudioJourneyHint(journey)}
      </p>
    </nav>
  );
}
