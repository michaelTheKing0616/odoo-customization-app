"use client";

import type { ReactNode } from "react";
import type { BulkGuide } from "@/lib/bulkSuiteScreen";
import { sanitizeBulkCopy } from "@/lib/bulkSuiteScreen";

type BulkStateGuideProps = {
  guide: BulkGuide;
  tone?: "neutral" | "warning" | "danger" | "accent";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** What happened, why, and what to do next. Quiet block, no nested cards. */
export function BulkStateGuide({
  guide,
  tone = "neutral",
  actions,
  testId,
  live = false,
  className,
  children,
}: BulkStateGuideProps) {
  return (
    <div
      className={["bu-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="bu-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {sanitizeBulkCopy(guide.title)}
      </p>
      <dl className="bu-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>{sanitizeBulkCopy(guide.why)}</dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>{sanitizeBulkCopy(guide.next)}</dd>
      </dl>
      {children}
      {actions ? <div className="bu-guide-actions">{actions}</div> : null}
    </div>
  );
}
