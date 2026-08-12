"use client";

import { IconExpert } from "@/components/ui/icons";
import { Tooltip } from "@/components/ui/Tooltip";
import { useShell } from "@/context/ShellContext";
import { cn } from "@/lib/cn";

type Props = {
  className?: string;
};

export function ExpertBubble({ className }: Props) {
  const { expertOpen, openExpert } = useShell();

  if (expertOpen) return null;

  return (
    <div
      className={cn(
        "pointer-events-none fixed bottom-6 right-6 z-[70] flex flex-col items-end gap-2",
        className,
      )}
    >
      <p
        className="pointer-events-none hidden rounded-full border border-accent/20 bg-surface-raised/95 px-3 py-1 text-xs text-muted shadow-sm backdrop-blur-sm sm:block"
        aria-hidden
      >
        Ask Odoo Expert
      </p>
      <Tooltip label="Open Odoo Expert — grounded answers with citations">
        <button
          type="button"
          data-testid="expert-bubble"
          aria-label="Open Odoo Expert"
          onClick={() => openExpert()}
          className={cn(
            "pointer-events-auto group relative flex h-14 w-14 items-center justify-center rounded-full",
            "bg-gradient-to-br from-accent to-accent-hover text-on-accent shadow-lg",
            "ring-4 ring-accent/15 transition-transform duration-200 hover:scale-105 hover:shadow-xl",
            "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-accent/40",
            "motion-safe:animate-[expert-bubble-float_4s_ease-in-out_infinite]",
          )}
        >
          <span
            className="absolute inset-0 rounded-full bg-accent/30 opacity-60 blur-md motion-safe:animate-pulse"
            aria-hidden
          />
          <IconExpert className="relative h-6 w-6 drop-shadow-sm transition-transform group-hover:scale-110" />
        </button>
      </Tooltip>
    </div>
  );
}
