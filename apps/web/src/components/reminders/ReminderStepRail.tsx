"use client";

import { REMINDER_STEPS, type ReminderStepId } from "@/lib/remindersScreen";

const STEP_IDS: ReminderStepId[] = ["compose", "schedule", "confirm", "created"];

type ReminderStepRailProps = {
  current: ReminderStepId;
};

export function ReminderStepRail({ current }: ReminderStepRailProps) {
  const currentIndex = STEP_IDS.indexOf(current);
  return (
    <ol
      className="rm-rail"
      data-testid="reminders-step-rail"
      aria-label="Reminders stages"
    >
      {REMINDER_STEPS.map((label, i) => {
        const id = STEP_IDS[i];
        const state = i < currentIndex ? "done" : i === currentIndex ? "current" : "todo";
        return (
          <li
            key={id}
            className="rm-rail-step"
            data-state={state}
            data-testid={`reminders-step-${id}`}
            aria-current={state === "current" ? "step" : undefined}
          >
            <span className="rm-rail-index" aria-hidden>
              {i + 1}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
