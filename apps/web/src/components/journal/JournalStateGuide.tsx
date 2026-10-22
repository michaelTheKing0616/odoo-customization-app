"use client";

import type { ReactNode } from "react";
import type { JournalStateGuide } from "@/lib/journalScreen";
import { sanitizeJournalCopy } from "@/lib/journalScreen";

type JournalStateGuideProps = {
  guide: JournalStateGuide;
  tone?: "neutral" | "warning" | "danger" | "accent" | "success";
  density?: "card" | "brief";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** What / why / next. Brief density avoids twin-banner with studio honesty. */
export function JournalStateGuide({
  guide,
  tone = "neutral",
  density = "card",
  actions,
  testId,
  live = false,
  className,
  children,
}: JournalStateGuideProps) {
  if (density === "brief") {
    return (
      <div
        className={["op-brief", className].filter(Boolean).join(" ")}
        data-testid={testId}
        role={live ? "alert" : undefined}
      >
        <p className="op-brief-title" data-testid={testId ? `${testId}-title` : undefined}>
          {sanitizeJournalCopy(guide.title)}
        </p>
        <dl className="op-brief-rows">
          <dt>Why</dt>
          <dd data-testid={testId ? `${testId}-why` : undefined}>
            {sanitizeJournalCopy(guide.why)}
          </dd>
          <dt>Next</dt>
          <dd data-testid={testId ? `${testId}-next` : undefined}>
            {sanitizeJournalCopy(guide.next)}
          </dd>
        </dl>
        {children}
        {actions ? <div className="jn-guide-actions">{actions}</div> : null}
      </div>
    );
  }

  return (
    <div
      className={["jn-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="jn-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {sanitizeJournalCopy(guide.title)}
      </p>
      <dl className="jn-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>
          {sanitizeJournalCopy(guide.why)}
        </dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>
          {sanitizeJournalCopy(guide.next)}
        </dd>
      </dl>
      {children}
      {actions ? <div className="jn-guide-actions">{actions}</div> : null}
    </div>
  );
}
