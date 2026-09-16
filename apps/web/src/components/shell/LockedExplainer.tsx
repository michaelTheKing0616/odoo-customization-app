"use client";

import Link from "next/link";
import { Callout } from "@/components/ui/Callout";
import { Button } from "@/components/ui/Button";
import { expertDestinationHref } from "@/lib/expert-journey";

export type LockedExplainerProps = {
  title: string;
  why: string;
  options?: string[];
  connectionId?: string;
  className?: string;
};

/**
 * Calm “why is this locked?” explainer (Build Spec delight / UI DESIGN BOT forbidden state).
 * Does not soften safety — states the gate and optional next paths.
 */
export function LockedExplainer({
  title,
  why,
  options = [],
  connectionId,
  className,
}: LockedExplainerProps) {
  return (
    <Callout
      variant="warning"
      title={title}
      className={className}
      testId="locked-explainer"
      actions={
        connectionId ? (
          <Button asChild size="sm" variant="ghost">
            <Link href={expertDestinationHref(connectionId)}>Ask Expert why</Link>
          </Button>
        ) : undefined
      }
    >
      <p data-testid="locked-explainer-why">{why}</p>
      {options.length > 0 ? (
        <ul className="mt-3 list-disc space-y-1 pl-5" data-testid="locked-explainer-options">
          {options.map((opt) => (
            <li key={opt}>{opt}</li>
          ))}
        </ul>
      ) : null}
    </Callout>
  );
}
