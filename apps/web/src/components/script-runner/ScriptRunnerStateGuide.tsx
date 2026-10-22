"use client";

import type { ReactNode } from "react";
import type { ScriptRunnerGuide } from "@/lib/scriptRunnerScreen";
import { sanitizeScriptRunnerCopy } from "@/lib/scriptRunnerScreen";

type ScriptRunnerStateGuideProps = {
  guide: ScriptRunnerGuide;
  tone?: "neutral" | "warning" | "danger" | "accent" | "success";
  density?: "card" | "brief";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** What happened, why, next. Brief density avoids twin-banner with studio honesty. */
export function ScriptRunnerStateGuide({
  guide,
  tone = "neutral",
  density = "card",
  actions,
  testId,
  live = false,
  className,
  children,
}: ScriptRunnerStateGuideProps) {
  if (density === "brief") {
    return (
      <div
        className={["op-brief", className].filter(Boolean).join(" ")}
        data-testid={testId}
        role={live ? "alert" : undefined}
      >
        <p className="op-brief-title" data-testid={testId ? `${testId}-title` : undefined}>
          {sanitizeScriptRunnerCopy(guide.title)}
        </p>
        <dl className="op-brief-rows">
          <dt>Why</dt>
          <dd data-testid={testId ? `${testId}-why` : undefined}>
            {sanitizeScriptRunnerCopy(guide.why)}
          </dd>
          <dt>Next</dt>
          <dd data-testid={testId ? `${testId}-next` : undefined}>
            {sanitizeScriptRunnerCopy(guide.next)}
          </dd>
        </dl>
        {children}
        {actions ? <div className="sr-guide-actions">{actions}</div> : null}
      </div>
    );
  }

  return (
    <div
      className={["sr-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="sr-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {sanitizeScriptRunnerCopy(guide.title)}
      </p>
      <dl className="sr-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>
          {sanitizeScriptRunnerCopy(guide.why)}
        </dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>
          {sanitizeScriptRunnerCopy(guide.next)}
        </dd>
      </dl>
      {children}
      {actions ? <div className="sr-guide-actions">{actions}</div> : null}
    </div>
  );
}
