"use client";

import type { ReactNode } from "react";

export type AutomationsGuide = {
  title: string;
  why: string;
  next: string;
};

type AutomationsStateGuideProps = {
  guide: AutomationsGuide;
  tone?: "neutral" | "warning" | "danger" | "accent";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** What happened, why, and what to do next. Quiet block, no nested cards. */
export function AutomationsStateGuide({
  guide,
  tone = "neutral",
  actions,
  testId,
  live = false,
  className,
  children,
}: AutomationsStateGuideProps) {
  return (
    <div
      className={["au-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="au-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {guide.title}
      </p>
      <dl className="au-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>{guide.why}</dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>{guide.next}</dd>
      </dl>
      {children}
      {actions ? <div className="au-guide-actions">{actions}</div> : null}
    </div>
  );
}
