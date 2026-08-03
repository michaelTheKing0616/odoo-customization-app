"use client";

import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
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
    <Callout
      variant="warning"
      title={gating.title}
      className={className}
      testId="gating-callout"
      actions={
        gating.gating_choices.length > 0 ? (
          <>
            {gating.gating_choices.map((choice) => (
              <Button
                key={choice.id}
                type="button"
                size="sm"
                variant={selectedChoice === choice.id ? "secondary" : "ghost"}
                data-testid={`gating-choice-${choice.id}`}
                onClick={() => onSelectChoice(choice.id as GatingChoiceId)}
              >
                {choice.label}
              </Button>
            ))}
          </>
        ) : undefined
      }
    >
      <p data-testid="gating-why">{gating.why}</p>
      {gating.options.length > 0 ? (
        <ul className="mt-3 list-disc space-y-1 pl-5" data-testid="gating-options">
          {gating.options.map((opt) => (
            <li key={opt}>{opt}</li>
          ))}
        </ul>
      ) : null}
    </Callout>
  );
}
