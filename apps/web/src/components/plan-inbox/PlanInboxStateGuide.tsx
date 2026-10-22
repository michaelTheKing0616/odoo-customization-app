"use client";

import type { ReactNode } from "react";
import type { PlanInboxGuide } from "@/lib/planInboxScreen";
import { sanitizePlanInboxCopy } from "@/lib/planInboxScreen";

type PlanInboxStateGuideProps = {
  guide: PlanInboxGuide;
  tone?: "neutral" | "info" | "warning" | "danger" | "success";
  /** `sheet` sits on the canvas in place of a plan; `inline` sits inside a panel. */
  variant?: "inline" | "sheet";
  actions?: ReactNode;
  testId?: string;
  /** Announce as an alert (errors) or a polite status (results). */
  live?: "alert" | "status";
  className?: string;
};

/** What happened, why, and the next step, set as prose rather than a table. */
export function PlanInboxStateGuide({
  guide,
  tone = "neutral",
  variant = "inline",
  actions,
  testId,
  live,
  className,
}: PlanInboxStateGuideProps) {
  return (
    <div
      className={["pi-note", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-variant={variant}
      data-testid={testId}
      role={live}
    >
      <p className="pi-note-title" data-testid={testId ? `${testId}-title` : undefined}>
        {sanitizePlanInboxCopy(guide.title)}
      </p>
      <p className="pi-note-why" data-testid={testId ? `${testId}-why` : undefined}>
        {sanitizePlanInboxCopy(guide.why)}
      </p>
      <p className="pi-note-next" data-testid={testId ? `${testId}-next` : undefined}>
        <span className="pi-note-label">Next</span>
        <span>{sanitizePlanInboxCopy(guide.next)}</span>
      </p>
      {actions ? <div className="pi-note-actions">{actions}</div> : null}
    </div>
  );
}
