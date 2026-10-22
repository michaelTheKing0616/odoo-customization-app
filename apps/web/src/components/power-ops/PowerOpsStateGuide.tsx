"use client";

import type { ReactNode } from "react";
import type { PowerOpsGuide } from "@/lib/powerOpsScreen";
import { sanitizePowerOpsCopy } from "@/lib/powerOpsScreen";

type PowerOpsStateGuideProps = {
  guide: PowerOpsGuide;
  tone?: "neutral" | "warning" | "danger" | "accent";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** What happened, why, and what to do next. Quiet block, no nested cards. */
export function PowerOpsStateGuide({
  guide,
  tone = "neutral",
  actions,
  testId,
  live = false,
  className,
  children,
}: PowerOpsStateGuideProps) {
  return (
    <div
      className={["po-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="po-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {sanitizePowerOpsCopy(guide.title)}
      </p>
      <dl className="po-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>
          {sanitizePowerOpsCopy(guide.why)}
        </dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>
          {sanitizePowerOpsCopy(guide.next)}
        </dd>
      </dl>
      {children}
      {actions ? <div className="po-guide-actions">{actions}</div> : null}
    </div>
  );
}
