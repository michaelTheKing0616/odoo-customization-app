"use client";

import { cn } from "@/lib/cn";
import type { DeploymentPanel } from "@/lib/api";
import { Card } from "@/components/ui/layout-primitives";

export type SandboxDeployPhaseId =
  | "package"
  | "sandbox"
  | "validate"
  | "promote";

export type SandboxDeployPhase = {
  id: SandboxDeployPhaseId;
  label: string;
  hint: string;
};

export const SANDBOX_DEPLOY_PHASES: SandboxDeployPhase[] = [
  {
    id: "package",
    label: "Package",
    hint: "Export x_* / inherit module zip",
  },
  {
    id: "sandbox",
    label: "Sandbox",
    hint: "Install & smoke on a matching-major sandbox",
  },
  {
    id: "validate",
    label: "Validate",
    hint: "Checks pass — ready window before promote",
  },
  {
    id: "promote",
    label: "Promote",
    hint: "Human confirm only — never auto-promote",
  },
];

type Props = {
  /** Index of the current phase (0–3). Completed phases are before it. */
  currentIndex: number;
  failed?: boolean;
  deploymentPanel?: DeploymentPanel | null;
  logTail?: string | null;
  approximation?: string | null;
  className?: string;
};

/**
 * Vercel-style sandbox → promote stage strip for Overview / export tab.
 * Honesty: promote stays human; sandbox-pending is never shown as “done”.
 */
export function SandboxDeployStages({
  currentIndex,
  failed = false,
  deploymentPanel,
  logTail,
  approximation,
  className,
}: Props) {
  const idx = Math.max(0, Math.min(currentIndex, SANDBOX_DEPLOY_PHASES.length - 1));

  return (
    <Card
      className={cn("mt-4 p-4", className)}
      data-testid="sandbox-deploy-stages"
    >
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
        Sandbox deploy
      </p>
      <h3 className="mt-1 text-base font-semibold text-ink">
        Package → sandbox → validate → promote
      </h3>
      <p className="mt-1 text-sm text-muted">
        Same honesty dialect as Job Autopilot: sandbox before promote; production Autopilot
        refuses; you confirm the last step.
      </p>

      <ol className="mt-4 grid gap-2 sm:grid-cols-4" data-testid="sandbox-deploy-phase-list">
        {SANDBOX_DEPLOY_PHASES.map((phase, i) => {
          const done = i < idx;
          const current = i === idx;
          return (
            <li
              key={phase.id}
              className={cn(
                "rounded border border-border-subtle bg-surface-muted px-3 py-2",
                done && "border-accent/30",
                current && !failed && "border-accent/50",
                current && failed && "border-danger/50",
              )}
              data-phase={phase.id}
              aria-current={current ? "step" : undefined}
            >
              <p className="text-[11px] font-medium uppercase tracking-wide text-muted">
                {i + 1}. {done ? "Done" : current ? (failed ? "Failed" : "Now") : "Next"}
              </p>
              <p className="mt-0.5 text-sm font-medium text-ink">{phase.label}</p>
              <p className="mt-0.5 text-xs text-muted">{phase.hint}</p>
            </li>
          );
        })}
      </ol>

      {deploymentPanel ? (
        <div
          className="mt-4 rounded border border-border-subtle bg-surface-muted p-3 text-sm"
          data-testid="deployment-panel"
        >
          <p className="font-medium text-ink">{deploymentPanel.title}</p>
          <p className="mt-2 text-muted">{deploymentPanel.body}</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-muted">
            {deploymentPanel.options.map((opt) => (
              <li key={opt}>{opt}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {approximation ? (
        <p
          className="mt-3 rounded border border-warning/40 bg-warning-subtle p-3 text-sm text-warning"
          data-testid="sandbox-approximation"
        >
          {approximation}
        </p>
      ) : null}

      {logTail ? (
        <details className="mt-3 border border-border-subtle bg-surface-muted p-3">
          <summary className="cursor-pointer text-sm text-muted hover:text-ink">
            Sandbox log
          </summary>
          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs text-muted">
            {logTail}
          </pre>
        </details>
      ) : null}
    </Card>
  );
}

/** Derive stage index from overview export/sandbox/promote state. */
export function sandboxDeployCurrentIndex(opts: {
  hasValidationId: boolean;
  promotedCount: number;
  sandboxBusy?: boolean;
  sandboxFailed?: boolean;
}): number {
  if (opts.promotedCount > 0) return 3;
  if (opts.hasValidationId) return 2;
  if (opts.sandboxBusy || opts.sandboxFailed) return 1;
  return 0;
}
