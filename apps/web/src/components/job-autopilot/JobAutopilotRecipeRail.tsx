"use client";

import { cn } from "@/lib/cn";
import {
  JOB_CONNECTOR_RECIPE,
  jobConnectorRecipeSteps,
  jobConnectorStepState,
} from "@/lib/job-autopilot-journey";

type ConnectorsResult = {
  ran?: string[];
  failed?: string[];
  skipped_ids?: string[];
  steps?: Array<{ name: string; ok: boolean }>;
} | null;

type JobAutopilotRecipeRailProps = {
  detected?: string[] | null;
  connectors?: ConnectorsResult;
  /** When true, show all five lanes even if none were detected (plan honesty). */
  showAllWhenEmpty?: boolean;
};

export function JobAutopilotRecipeRail({
  detected,
  connectors,
  showAllWhenEmpty = true,
}: JobAutopilotRecipeRailProps) {
  const hasDetected = Boolean(detected?.length);
  if (!hasDetected && !showAllWhenEmpty && !connectors) return null;

  const steps = hasDetected
    ? jobConnectorRecipeSteps(detected)
    : JOB_CONNECTOR_RECIPE.map((row) => ({ ...row, active: false }));

  return (
    <nav
      className="job-recipe-rail"
      aria-label="Connector recipe order"
      data-testid="job-recipe-rail"
    >
      <p className="job-recipe-rail-title">Connector recipe</p>
      <ol className="job-recipe-list">
        {steps.map((step) => {
          const state = connectors
            ? jobConnectorStepState(step.id, connectors)
            : step.active
              ? "queued"
              : "idle";
          return (
            <li
              key={step.id}
              className={cn(
                "job-recipe-step",
                step.active && "is-active",
                state === "done" && "is-done",
                state === "failed" && "is-failed",
                state === "skipped" && "is-skipped",
                state === "queued" && step.active && "is-queued",
              )}
              data-recipe={step.id}
              data-state={state}
            >
              <span className="job-recipe-label">{step.label}</span>
              <span className="job-recipe-state" aria-hidden>
                {state === "done"
                  ? "Smoke ok"
                  : state === "failed"
                    ? "Gap"
                    : state === "skipped"
                      ? "Skipped"
                      : step.active
                        ? "In plan"
                        : "Off"}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="job-recipe-hint">
        Order is fixed: payments, inbound orders, messaging, hardware, statutory. Smoke
        result per path. Publishing stays a step you confirm.
      </p>
    </nav>
  );
}
