"use client";

import type { ReactNode } from "react";
import type { LiveDemoGuide } from "@/lib/liveDemoCopilotScreen";
import { sanitizeLiveDemoCopy } from "@/lib/liveDemoCopilotScreen";

type LiveDemoStateGuideProps = {
  guide: LiveDemoGuide;
  tone?: "neutral" | "warning" | "danger" | "accent" | "success";
  density?: "card" | "brief";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** What / why / next. Brief density avoids twin-banner with studio honesty. */
export function LiveDemoStateGuide({
  guide,
  tone = "neutral",
  density = "card",
  actions,
  testId,
  live = false,
  className,
  children,
}: LiveDemoStateGuideProps) {
  if (density === "brief") {
    return (
      <div
        className={["op-brief", className].filter(Boolean).join(" ")}
        data-testid={testId}
        role={live ? "alert" : undefined}
      >
        <p className="op-brief-title" data-testid={testId ? `${testId}-title` : undefined}>
          {sanitizeLiveDemoCopy(guide.title)}
        </p>
        <dl className="op-brief-rows">
          <dt>Why</dt>
          <dd data-testid={testId ? `${testId}-why` : undefined}>
            {sanitizeLiveDemoCopy(guide.why)}
          </dd>
          <dt>Next</dt>
          <dd data-testid={testId ? `${testId}-next` : undefined}>
            {sanitizeLiveDemoCopy(guide.next)}
          </dd>
        </dl>
        {children}
        {actions ? <div className="ldc-guide-actions">{actions}</div> : null}
      </div>
    );
  }

  return (
    <div
      className={["ldc-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="ldc-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {sanitizeLiveDemoCopy(guide.title)}
      </p>
      <dl className="ldc-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>
          {sanitizeLiveDemoCopy(guide.why)}
        </dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>
          {sanitizeLiveDemoCopy(guide.next)}
        </dd>
      </dl>
      {children}
      {actions ? <div className="ldc-guide-actions">{actions}</div> : null}
    </div>
  );
}
