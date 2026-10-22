"use client";

import type { ReactNode } from "react";
import type { ApprovalsGuide } from "@/lib/approvalScreen";

type ApprovalsStateGuideProps = {
  guide: ApprovalsGuide;
  tone?: "neutral" | "warning" | "danger" | "accent";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** What happened, why, and what to do next. Quiet block, no nested cards. */
export function ApprovalsStateGuide({
  guide,
  tone = "neutral",
  actions,
  testId,
  live = false,
  className,
  children,
}: ApprovalsStateGuideProps) {
  return (
    <div
      className={["ap-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="ap-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {guide.title}
      </p>
      <dl className="ap-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>{guide.why}</dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>{guide.next}</dd>
      </dl>
      {children}
      {actions ? <div className="ap-guide-actions">{actions}</div> : null}
    </div>
  );
}
