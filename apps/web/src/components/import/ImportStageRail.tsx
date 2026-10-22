"use client";

import { IMPORT_STEPS, type ImportStepIndex } from "@/lib/importScreen";

type ImportStageRailProps = {
  step: ImportStepIndex;
};

export function ImportStageRail({ step }: ImportStageRailProps) {
  return (
    <ol className="im-rail" data-testid="import-stage-rail" aria-label="Import stages">
      {IMPORT_STEPS.map((label, i) => {
        const index = (i + 1) as ImportStepIndex;
        const state = index < step ? "done" : index === step ? "current" : "todo";
        return (
          <li key={label} className="im-rail-step" data-state={state} data-testid={`import-step-${label.toLowerCase()}`}>
            <span className="im-rail-index" aria-hidden>
              {index}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
