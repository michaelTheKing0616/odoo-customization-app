"use client";

import type { ReactNode } from "react";
import type { IdGeneratorStateGuide } from "@/lib/idGeneratorScreen";
import { sanitizeIdGenCopy } from "@/lib/idGeneratorScreen";

type IdGeneratorStateGuideProps = {
  guide: IdGeneratorStateGuide;
  tone?: "neutral" | "warning" | "danger" | "accent" | "success";
  density?: "card" | "brief";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** What / why / next. Brief density avoids twin-banner with studio honesty. */
export function IdGeneratorStateGuide({
  guide,
  tone = "neutral",
  density = "card",
  actions,
  testId,
  live = false,
  className,
  children,
}: IdGeneratorStateGuideProps) {
  if (density === "brief") {
    return (
      <div
        className={["op-brief", className].filter(Boolean).join(" ")}
        data-testid={testId}
        role={live ? "alert" : undefined}
      >
        <p className="op-brief-title" data-testid={testId ? `${testId}-title` : undefined}>
          {sanitizeIdGenCopy(guide.title)}
        </p>
        <dl className="op-brief-rows">
          <dt>Why</dt>
          <dd data-testid={testId ? `${testId}-why` : undefined}>
            {sanitizeIdGenCopy(guide.why)}
          </dd>
          <dt>Next</dt>
          <dd data-testid={testId ? `${testId}-next` : undefined}>
            {sanitizeIdGenCopy(guide.next)}
          </dd>
        </dl>
        {children}
        {actions ? <div className="ig-guide-actions">{actions}</div> : null}
      </div>
    );
  }

  return (
    <div
      className={["ig-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="ig-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {sanitizeIdGenCopy(guide.title)}
      </p>
      <dl className="ig-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>
          {sanitizeIdGenCopy(guide.why)}
        </dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>
          {sanitizeIdGenCopy(guide.next)}
        </dd>
      </dl>
      {children}
      {actions ? <div className="ig-guide-actions">{actions}</div> : null}
    </div>
  );
}
