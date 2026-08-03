"use client";

import type { GatingCallout as GatingCalloutType, GatingChoiceId } from "@/lib/api";

type Props = {
  gating: GatingCalloutType;
  selectedChoice: GatingChoiceId | null;
  onSelectChoice: (choice: GatingChoiceId) => void;
  className?: string;
};

export function GatingCallout({
  gating,
  selectedChoice,
  onSelectChoice,
  className = "",
}: Props) {
  if (gating.available) {
    return null;
  }

  return (
    <div
      className={`rounded-md border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 ${className}`}
      data-testid="gating-callout"
      role="status"
    >
      <p className="font-medium" data-testid="gating-title">
        {gating.title}
      </p>
      <p className="mt-2 text-amber-900" data-testid="gating-why">
        {gating.why}
      </p>
      <ul className="mt-3 list-disc space-y-1 pl-5" data-testid="gating-options">
        {gating.options.map((opt) => (
          <li key={opt}>{opt}</li>
        ))}
      </ul>
      {gating.gating_choices.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-2" data-testid="gating-choices">
          {gating.gating_choices.map((choice) => (
            <button
              key={choice.id}
              type="button"
              data-testid={`gating-choice-${choice.id}`}
              className={`rounded border px-3 py-1.5 text-sm ${
                selectedChoice === choice.id
                  ? "border-amber-800 bg-amber-200 font-medium"
                  : "border-amber-400 bg-white hover:bg-amber-100"
              }`}
              onClick={() => onSelectChoice(choice.id as GatingChoiceId)}
            >
              {choice.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
