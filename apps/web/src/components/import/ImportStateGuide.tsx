"use client";

import type { ReactNode } from "react";
import type { ImportGuide } from "@/lib/importScreen";
import { sanitizeImportCopy } from "@/lib/importScreen";

type ImportStateGuideProps = {
  guide: ImportGuide;
  tone?: "neutral" | "warning" | "danger" | "accent";
  /** brief = compact paper intro (empty what/why/next). card = situational guide. */
  density?: "card" | "brief";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** What happened, why, next. Brief density avoids twin-banner with studio honesty. */
export function ImportStateGuide({
  guide,
  tone = "neutral",
  density = "card",
  actions,
  testId,
  live = false,
  className,
  children,
}: ImportStateGuideProps) {
  if (density === "brief") {
    return (
      <div
        className={["op-brief", className].filter(Boolean).join(" ")}
        data-testid={testId}
        role={live ? "alert" : undefined}
      >
        <p className="op-brief-title" data-testid={testId ? `${testId}-title` : undefined}>
          {sanitizeImportCopy(guide.title)}
        </p>
        <dl className="op-brief-rows">
          <dt>Why</dt>
          <dd data-testid={testId ? `${testId}-why` : undefined}>
            {sanitizeImportCopy(guide.why)}
          </dd>
          <dt>Next</dt>
          <dd data-testid={testId ? `${testId}-next` : undefined}>
            {sanitizeImportCopy(guide.next)}
          </dd>
        </dl>
        {children}
        {actions ? <div className="im-guide-actions">{actions}</div> : null}
      </div>
    );
  }

  return (
    <div
      className={["im-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="im-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {sanitizeImportCopy(guide.title)}
      </p>
      <dl className="im-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>
          {sanitizeImportCopy(guide.why)}
        </dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>
          {sanitizeImportCopy(guide.next)}
        </dd>
      </dl>
      {children}
      {actions ? <div className="im-guide-actions">{actions}</div> : null}
    </div>
  );
}
