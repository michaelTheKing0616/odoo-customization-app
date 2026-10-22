"use client";

import { cn } from "@/lib/cn";

export type IngestStepId = "upload" | "classify" | "plan" | "dry-run" | "commit";

const STEPS: { id: IngestStepId; label: string }[] = [
  { id: "upload", label: "Upload" },
  { id: "classify", label: "Classify" },
  { id: "plan", label: "Plan" },
  { id: "dry-run", label: "Test run" },
  { id: "commit", label: "Commit" },
];

export function resolveIngestStep(opts: {
  hasJob: boolean;
  needsTypeConfirm?: boolean;
  hasDryRunLog: boolean;
  hasCommitLog: boolean;
}): IngestStepId {
  if (opts.hasCommitLog) return "commit";
  if (opts.hasDryRunLog) return "dry-run";
  if (opts.hasJob && opts.needsTypeConfirm) return "classify";
  if (opts.hasJob) return "plan";
  return "upload";
}

export function IngestStepRail({
  current,
  className,
}: {
  current: IngestStepId;
  className?: string;
}) {
  const currentIndex = STEPS.findIndex((s) => s.id === current);
  return (
    <ol
      aria-label="Ingest steps"
      className={cn("ig-rail", className)}
      data-testid="ingest-step-rail"
    >
      {STEPS.map((step, index) => {
        const state = index < currentIndex ? "done" : index === currentIndex ? "current" : "todo";
        return (
          <li
            key={step.id}
            className="ig-rail-step"
            data-state={state}
            data-testid={`ingest-step-rail-${step.id}`}
            aria-current={state === "current" ? "step" : undefined}
          >
            <span className="ig-rail-index" aria-hidden>
              {index + 1}
            </span>
            <span>{step.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
