"use client";

import type { ReactNode } from "react";
import type { ReminderGuide } from "@/lib/remindersScreen";
import { sanitizeReminderCopy } from "@/lib/remindersScreen";

type ReminderStateGuideProps = {
  guide: ReminderGuide;
  tone?: "neutral" | "warning" | "danger" | "accent" | "success";
  /** brief = compact paper intro (empty what/why/next). card = situational guide. */
  density?: "card" | "brief";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** What happened, why, and what to do next. Brief density avoids twin-banner with honesty. */
export function ReminderStateGuide({
  guide,
  tone = "neutral",
  density = "card",
  actions,
  testId,
  live = false,
  className,
  children,
}: ReminderStateGuideProps) {
  if (density === "brief") {
    return (
      <div
        className={["rm-brief", className].filter(Boolean).join(" ")}
        data-testid={testId}
        role={live ? "alert" : undefined}
      >
        <p className="rm-brief-title" data-testid={testId ? `${testId}-title` : undefined}>
          {sanitizeReminderCopy(guide.title)}
        </p>
        <dl className="rm-brief-rows">
          <dt>Why</dt>
          <dd data-testid={testId ? `${testId}-why` : undefined}>
            {sanitizeReminderCopy(guide.why)}
          </dd>
          <dt>Next</dt>
          <dd data-testid={testId ? `${testId}-next` : undefined}>
            {sanitizeReminderCopy(guide.next)}
          </dd>
        </dl>
        {children}
        {actions ? <div className="rm-guide-actions">{actions}</div> : null}
      </div>
    );
  }

  return (
    <div
      className={["rm-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="rm-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {sanitizeReminderCopy(guide.title)}
      </p>
      <dl className="rm-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>
          {sanitizeReminderCopy(guide.why)}
        </dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>
          {sanitizeReminderCopy(guide.next)}
        </dd>
      </dl>
      {children}
      {actions ? <div className="rm-guide-actions">{actions}</div> : null}
    </div>
  );
}
