import { Check } from "@/components/ui/icons";
import type { RailStep } from "./code-studio-gate";

const STATE_LABEL: Record<RailStep["state"], string> = {
  done: "done",
  current: "next",
  blocked: "needs a fix",
  todo: "locked",
  optional: "optional",
};

/** Write, Validate, (Test), Bind or Download. Shows where the authoring gate stands. */
export function CodeStudioGateRail({ steps, summary }: { steps: RailStep[]; summary: string }) {
  return (
    <nav aria-label="Code Studio steps" className="cs-rail" data-testid="code-studio-gate-rail">
      <ol className="cs-rail-list">
        {steps.map((step, index) => (
          <li
            key={step.key}
            className="cs-rail-step"
            data-state={step.state}
            data-testid={`code-studio-step-${step.key}`}
            aria-current={step.state === "current" ? "step" : undefined}
          >
            <span className="cs-rail-mark" aria-hidden="true">
              {step.state === "done" ? (
                <Check className="h-3 w-3" strokeWidth={2.5} />
              ) : step.state === "blocked" ? (
                "!"
              ) : (
                index + 1
              )}
            </span>
            <span className="cs-rail-text">
              <span className="cs-rail-label">{step.label}</span>
              <span className="cs-rail-detail">
                {step.detail}
                <span className="sr-only">, {STATE_LABEL[step.state]}</span>
              </span>
            </span>
          </li>
        ))}
      </ol>
      <p className="cs-rail-summary" role="status" aria-live="polite" data-testid="code-studio-gate-summary">
        {summary}
      </p>
    </nav>
  );
}
