"use client";

import { cn } from "@/lib/cn";

export type HousekeepingStepId = "scan" | "review" | "dry-run" | "clean";

const STEPS: { id: HousekeepingStepId; label: string }[] = [
  { id: "scan", label: "Scan" },
  { id: "review", label: "Review" },
  { id: "dry-run", label: "Test run" },
  { id: "clean", label: "Clean" },
];

export function resolveHousekeepingStep(opts: {
  hasScan: boolean;
  hasSelection: boolean;
  hasDryRunResult: boolean;
  hasCleanResult: boolean;
}): HousekeepingStepId {
  if (opts.hasCleanResult) return "clean";
  if (opts.hasDryRunResult) return "dry-run";
  if (opts.hasScan || opts.hasSelection) return "review";
  return "scan";
}

export function HousekeepingStepRail({
  current,
  className,
}: {
  current: HousekeepingStepId;
  className?: string;
}) {
  const currentIndex = STEPS.findIndex((s) => s.id === current);
  return (
    <nav
      aria-label="Housekeeping steps"
      className={cn("overflow-x-auto", className)}
      data-testid="housekeeping-step-rail"
    >
      <ol className="flex min-w-max items-center gap-1 text-xs">
        {STEPS.map((step, index) => {
          const done = index < currentIndex;
          const active = index === currentIndex;
          return (
            <li key={step.id} className="flex items-center gap-1">
              {index > 0 ? (
                <span
                  aria-hidden
                  className={cn(
                    "mx-1 h-px w-4 sm:w-6",
                    done || active ? "bg-accent/50" : "bg-border-subtle",
                  )}
                />
              ) : null}
              <span
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-medium transition-colors duration-[80ms]",
                  active &&
                    "border-accent/40 bg-accent/10 text-accent ring-1 ring-accent/20",
                  done && !active && "border-border-subtle bg-surface-muted text-ink",
                  !done && !active && "border-transparent text-muted",
                )}
                aria-current={active ? "step" : undefined}
                data-testid={`housekeeping-step-rail-${step.id}`}
                data-active={active ? "true" : undefined}
              >
                <span
                  className={cn(
                    "inline-flex size-4 items-center justify-center rounded-full text-[10px] tabular-nums",
                    active && "bg-accent text-on-accent",
                    done && !active && "bg-surface-raised text-muted",
                    !done && !active && "bg-surface-muted text-muted",
                  )}
                  aria-hidden
                >
                  {index + 1}
                </span>
                {step.label}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
