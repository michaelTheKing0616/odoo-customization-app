"use client";

import { Callout } from "@/components/ui/Callout";
import {
  buildConnectChecklist,
  hostCapabilityBullets,
  type ConnectChecklistInput,
} from "@/lib/connect-checklist";
import { cn } from "@/lib/cn";

type Props = {
  input: ConnectChecklistInput;
  className?: string;
  /** When verified, show host capability bullets under the checklist. */
  showCapabilities?: boolean;
};

export function ConnectChecklist({ input, className, showCapabilities }: Props) {
  const { kind, steps, completed, total } = buildConnectChecklist(input);
  const bullets = hostCapabilityBullets(kind);

  return (
    <div
      className={cn(
        "rounded-lg border border-border bg-surface p-4 shadow-sm",
        className,
      )}
      data-testid="connect-checklist"
    >
      <div className="mb-3 flex items-baseline justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">Connect checklist</h2>
          <p className="mt-0.5 text-xs text-muted">
            Live guide for Online, Odoo.sh, Community, Enterprise, and on-prem.
          </p>
        </div>
        <p className="shrink-0 text-xs font-medium tabular-nums text-muted" data-testid="connect-checklist-progress">
          {completed}/{total}
        </p>
      </div>
      <ol className="space-y-2">
        {steps.map((step, index) => (
          <li
            key={step.id}
            className={cn(
              "flex gap-3 rounded-md border px-3 py-2 text-sm",
              step.done
                ? "border-success/30 bg-success/10"
                : step.emphasis === "warn"
                  ? "border-warning/30 bg-warning/10"
                  : "border-border/80 bg-surface",
            )}
            data-testid={`connect-checklist-step-${step.id}`}
            data-done={step.done ? "true" : "false"}
          >
            <span
              className={cn(
                "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold",
                step.done
                  ? "bg-success text-white"
                  : "bg-muted/30 text-muted",
              )}
              aria-hidden
            >
              {step.done ? "✓" : index + 1}
            </span>
            <div className="min-w-0">
              <p className="font-medium text-ink">{step.label}</p>
              <p className="mt-0.5 text-xs text-muted">{step.detail}</p>
            </div>
          </li>
        ))}
      </ol>
      {showCapabilities || completed >= 4 ? (
        <Callout
          variant="info"
          title={
            kind === "online"
              ? "On this host (Odoo Online)"
              : kind === "odoo_sh"
                ? "On this host (Odoo.sh)"
                : kind === "self_hosted"
                  ? "On this host (self-hosted)"
                  : "What to expect"
          }
          className="mt-3"
          testId="connect-host-capabilities"
        >
          <ul className="list-disc space-y-1 pl-4">
            {bullets.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </Callout>
      ) : null}
    </div>
  );
}
