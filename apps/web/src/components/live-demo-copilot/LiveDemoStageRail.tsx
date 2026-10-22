"use client";

import { LIVE_DEMO_STEPS, type LiveDemoStepIndex } from "@/lib/liveDemoCopilotScreen";

type LiveDemoStageRailProps = {
  step: LiveDemoStepIndex;
};

export function LiveDemoStageRail({ step }: LiveDemoStageRailProps) {
  return (
    <ol
      className="ldc-rail"
      data-testid="live-demo-stage-rail"
      aria-label="Live Demo Co-Pilot stages"
    >
      {LIVE_DEMO_STEPS.map((label, i) => {
        const index = (i + 1) as LiveDemoStepIndex;
        const state = index < step ? "done" : index === step ? "current" : "todo";
        return (
          <li
            key={label}
            className="ldc-rail-step"
            data-state={state}
            aria-current={state === "current" ? "step" : undefined}
            data-testid={`live-demo-step-${label.toLowerCase()}`}
          >
            <span className="ldc-rail-index" aria-hidden>
              {index}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
