"use client";

import { CRON_STEPS, type CronStepId } from "@/lib/cronManagerScreen";

const STEP_IDS: CronStepId[] = ["list", "select", "trigger", "save"];

type CronStepRailProps = {
  current: CronStepId;
};

export function CronStepRail({ current }: CronStepRailProps) {
  const currentIndex = STEP_IDS.indexOf(current);
  return (
    <ol className="cr-rail" data-testid="cron-stage-rail" aria-label="Cron Manager stages">
      {CRON_STEPS.map((label, i) => {
        const id = STEP_IDS[i];
        const state = i < currentIndex ? "done" : i === currentIndex ? "current" : "todo";
        return (
          <li
            key={id}
            className="cr-rail-step"
            data-state={state}
            data-testid={`cron-step-${id}`}
            aria-current={state === "current" ? "step" : undefined}
          >
            <span className="cr-rail-index" aria-hidden>
              {i + 1}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
