"use client";

import type { ReactNode } from "react";
import type { OpsHubGuide } from "@/lib/operationsHubScreen";
import { sanitizeOpsHubCopy } from "@/lib/operationsHubScreen";

type OpsHubStateGuideProps = {
  guide: OpsHubGuide;
  tone?: "neutral" | "warning" | "danger" | "accent";
  /** callout = risk/state panel; caption = quiet one-liner (default for non-imminent). */
  density?: "callout" | "caption";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** Orientation and honesty. Prefer caption; callout only when risk or failure is imminent. */
export function OpsHubStateGuide({
  guide,
  tone = "neutral",
  density = "callout",
  actions,
  testId,
  live = false,
  className,
  children,
}: OpsHubStateGuideProps) {
  if (density === "caption") {
    return (
      <aside
        className={["oh-caption", className].filter(Boolean).join(" ")}
        data-tone={tone}
        data-testid={testId}
        role={live ? "alert" : undefined}
      >
        <p className="oh-caption-title" data-testid={testId ? `${testId}-title` : undefined}>
          {sanitizeOpsHubCopy(guide.title)}
        </p>
        <p className="oh-caption-body">
          <span data-testid={testId ? `${testId}-why` : undefined}>
            {sanitizeOpsHubCopy(guide.why)}
          </span>{" "}
          <span data-testid={testId ? `${testId}-next` : undefined}>
            {sanitizeOpsHubCopy(guide.next)}
          </span>
        </p>
        {children}
        {actions ? <div className="oh-guide-actions">{actions}</div> : null}
      </aside>
    );
  }

  return (
    <div
      className={["oh-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="oh-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {sanitizeOpsHubCopy(guide.title)}
      </p>
      <dl className="oh-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>
          {sanitizeOpsHubCopy(guide.why)}
        </dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>
          {sanitizeOpsHubCopy(guide.next)}
        </dd>
      </dl>
      {children}
      {actions ? <div className="oh-guide-actions">{actions}</div> : null}
    </div>
  );
}
