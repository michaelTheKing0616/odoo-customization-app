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
      <p className="expert-launcher-hint pointer-events-none hidden sm:block" aria-hidden>
        Odoo Expert
      </p>
      <Tooltip label="Open Odoo Expert — grounded answers, never auto-promotes">
        <button
          type="button"
          data-testid="open-expert"
          aria-label="Open Odoo Expert"
          onClick={() => openExpert()}
          className={cn(
            "expert-launcher pointer-events-auto group relative flex h-12 w-12 items-center justify-center rounded-full",
            "bg-accent text-on-accent shadow-lg",
            "ring-4 ring-accent/10 transition-transform duration-200 hover:scale-[1.04] hover:bg-accent-hover hover:shadow-xl",
            "focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-accent/40",
          )}
        >
          <IconExpert className="relative h-5 w-5 transition-transform group-hover:scale-110" />
        </button>
      </Tooltip>
    </div>
  );
}
