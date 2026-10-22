"use client";

import { JOURNAL_STEPS, type JournalStepIndex } from "@/lib/journalScreen";

type JournalStageRailProps = {
  step: JournalStepIndex;
};

export function JournalStageRail({ step }: JournalStageRailProps) {
  return (
    <ol className="jn-rail" data-testid="journal-stage-rail" aria-label="Change journal stages">
      {JOURNAL_STEPS.map((label, i) => {
        const index = (i + 1) as JournalStepIndex;
        const state = index < step ? "done" : index === step ? "current" : "todo";
        const slug = label.toLowerCase().replace(/\s+/g, "-");
        return (
          <li
            key={label}
            className="jn-rail-step"
            data-state={state}
            aria-current={state === "current" ? "step" : undefined}
            data-testid={`journal-step-${slug}`}
          >
            <span className="jn-rail-index" aria-hidden>
              {index}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
