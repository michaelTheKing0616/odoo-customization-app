"use client";

import type { ReactNode } from "react";
import type { CronGuide } from "@/lib/cronManagerScreen";
import { sanitizeCronCopy } from "@/lib/cronManagerScreen";

type CronStateGuideProps = {
  guide: CronGuide;
  tone?: "neutral" | "warning" | "danger" | "accent";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** What happened, why, and what to do next. Quiet block, no nested cards. */
export function CronStateGuide({
  guide,
  tone = "neutral",
  actions,
  testId,
  live = false,
  className,
  children,
}: CronStateGuideProps) {
  return (
    <div
      className={["cr-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="cr-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {sanitizeCronCopy(guide.title)}
      </p>
      <dl className="cr-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>{sanitizeCronCopy(guide.why)}</dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>{sanitizeCronCopy(guide.next)}</dd>
      </dl>
      {children}
      {actions ? <div className="cr-guide-actions">{actions}</div> : null}
    </div>
  );
}
