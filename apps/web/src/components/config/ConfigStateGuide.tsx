"use client";

import type { ReactNode } from "react";
import type { ConfigStateGuide } from "@/lib/configScreen";
import { sanitizeConfigCopy } from "@/lib/configScreen";

type ConfigStateGuideProps = {
  guide: ConfigStateGuide;
  tone?: "neutral" | "warning" | "danger" | "accent" | "success";
  density?: "card" | "brief";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** What / why / next. Brief density avoids twin-banner with studio honesty. */
export function ConfigStateGuide({
  guide,
  tone = "neutral",
  density = "card",
  actions,
  testId,
  live = false,
  className,
  children,
}: ConfigStateGuideProps) {
  if (density === "brief") {
    return (
      <div
        className={["op-brief", className].filter(Boolean).join(" ")}
        data-testid={testId}
        role={live ? "alert" : undefined}
      >
        <p className="op-brief-title" data-testid={testId ? `${testId}-title` : undefined}>
          {sanitizeConfigCopy(guide.title)}
        </p>
        <dl className="op-brief-rows">
          <dt>Why</dt>
          <dd data-testid={testId ? `${testId}-why` : undefined}>
            {sanitizeConfigCopy(guide.why)}
          </dd>
          <dt>Next</dt>
          <dd data-testid={testId ? `${testId}-next` : undefined}>
            {sanitizeConfigCopy(guide.next)}
          </dd>
        </dl>
        {children}
        {actions ? <div className="cfg-guide-actions">{actions}</div> : null}
      </div>
    );
  }

  return (
    <div
      className={["cfg-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="cfg-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {sanitizeConfigCopy(guide.title)}
      </p>
      <dl className="cfg-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>
          {sanitizeConfigCopy(guide.why)}
        </dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>
          {sanitizeConfigCopy(guide.next)}
        </dd>
      </dl>
      {children}
      {actions ? <div className="cfg-guide-actions">{actions}</div> : null}
    </div>
  );
}
