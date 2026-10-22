"use client";

import type { ReactNode } from "react";
import type { FleetGuide } from "@/lib/fleetCommandScreen";
import { sanitizeFleetCopy } from "@/lib/fleetCommandScreen";

type FleetStateGuideProps = {
  guide: FleetGuide;
  tone?: "neutral" | "warning" | "danger" | "accent";
  /** callout = risk/state panel; caption = quiet one-liner. */
  density?: "callout" | "caption";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** Orientation and honesty. Prefer caption; callout only when risk or failure is imminent. */
export function FleetStateGuide({
  guide,
  tone = "neutral",
  density = "callout",
  actions,
  testId,
  live = false,
  className,
  children,
}: FleetStateGuideProps) {
  if (density === "caption") {
    return (
      <aside
        className={["fc-caption", className].filter(Boolean).join(" ")}
        data-tone={tone}
        data-testid={testId}
        role={live ? "alert" : undefined}
      >
        <p className="fc-caption-title" data-testid={testId ? `${testId}-title` : undefined}>
          {sanitizeFleetCopy(guide.title)}
        </p>
        <p className="fc-caption-body">
          <span data-testid={testId ? `${testId}-why` : undefined}>
            {sanitizeFleetCopy(guide.why)}
          </span>{" "}
          <span data-testid={testId ? `${testId}-next` : undefined}>
            {sanitizeFleetCopy(guide.next)}
          </span>
        </p>
        {children}
        {actions ? <div className="fc-guide-actions">{actions}</div> : null}
      </aside>
    );
  }

  return (
    <div
      className={["fc-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="fc-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {sanitizeFleetCopy(guide.title)}
      </p>
      <dl className="fc-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>
          {sanitizeFleetCopy(guide.why)}
        </dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>
          {sanitizeFleetCopy(guide.next)}
        </dd>
      </dl>
      {children}
      {actions ? <div className="fc-guide-actions">{actions}</div> : null}
    </div>
  );
}
