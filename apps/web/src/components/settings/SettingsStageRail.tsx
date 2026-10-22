"use client";

import { SETTINGS_STEPS, type SettingsStepIndex } from "@/lib/settingsScreen";

type SettingsStageRailProps = {
  step: SettingsStepIndex;
};

export function SettingsStageRail({ step }: SettingsStageRailProps) {
  return (
    <ol className="stg-rail" data-testid="settings-stage-rail" aria-label="Settings stages">
      {SETTINGS_STEPS.map((label, i) => {
        const index = (i + 1) as SettingsStepIndex;
        const state = index < step ? "done" : index === step ? "current" : "todo";
        return (
          <li
            key={label}
            className="stg-rail-step"
            data-state={state}
            data-testid={`settings-step-${label.toLowerCase()}`}
            aria-current={state === "current" ? "step" : undefined}
          >
            <span className="stg-rail-index" aria-hidden>
              {index}
            </span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
