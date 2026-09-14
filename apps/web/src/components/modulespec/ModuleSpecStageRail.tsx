"use client";

import { cn } from "@/lib/cn";
import {
  MODULESPEC_STAGES,
  moduleSpecJourneyHint,
  type ModuleSpecJourneyState,
} from "@/lib/modulespec-journey";

type ModuleSpecStageRailProps = {
  journey: ModuleSpecJourneyState;
};

export function ModuleSpecStageRail({ journey }: ModuleSpecStageRailProps) {
  const currentIndex = MODULESPEC_STAGES.findIndex((row) => row.id === journey.id);
  return (
    <nav
      className="studio-stage-rail"
      aria-label="ModuleSpec stages"
      data-testid="modulespec-stage-rail"
    >
      <ol className="studio-stage-list" data-testid="modulespec-steps">
        {MODULESPEC_STAGES.map((stage, index) => {
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
      <p className="studio-stage-hint" data-testid="modulespec-stage-hint">
        {moduleSpecJourneyHint(journey)}
      </p>
    </nav>
  );
}
