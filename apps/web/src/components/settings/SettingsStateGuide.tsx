"use client";

import type { ReactNode } from "react";
import type { SettingsStateGuide } from "@/lib/settingsScreen";
import { sanitizeSettingsCopy } from "@/lib/settingsScreen";

type SettingsStateGuideProps = {
  guide: SettingsStateGuide;
  tone?: "neutral" | "warning" | "danger" | "accent" | "success";
  density?: "card" | "brief";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** What / why / next. Brief density avoids twin-banner with studio honesty. */
export function SettingsStateGuide({
  guide,
  tone = "neutral",
  density = "card",
  actions,
  testId,
  live = false,
  className,
  children,
}: SettingsStateGuideProps) {
  if (density === "brief") {
    return (
      <div
        className={["op-brief", className].filter(Boolean).join(" ")}
        data-testid={testId}
        role={live ? "alert" : undefined}
      >
        <p className="op-brief-title" data-testid={testId ? `${testId}-title` : undefined}>
          {sanitizeSettingsCopy(guide.title)}
        </p>
        <dl className="op-brief-rows">
          <dt>Why</dt>
          <dd data-testid={testId ? `${testId}-why` : undefined}>
            {sanitizeSettingsCopy(guide.why)}
          </dd>
          <dt>Next</dt>
          <dd data-testid={testId ? `${testId}-next` : undefined}>
            {sanitizeSettingsCopy(guide.next)}
          </dd>
        </dl>
        {children}
        {actions ? <div className="stg-guide-actions">{actions}</div> : null}
      </div>
    );
  }

  return (
    <div
      className={["stg-guide", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p className="stg-guide-title" data-testid={testId ? `${testId}-title` : undefined}>
        {sanitizeSettingsCopy(guide.title)}
      </p>
      <dl className="stg-guide-rows">
        <dt>Why</dt>
        <dd data-testid={testId ? `${testId}-why` : undefined}>
          {sanitizeSettingsCopy(guide.why)}
        </dd>
        <dt>Next</dt>
        <dd data-testid={testId ? `${testId}-next` : undefined}>
          {sanitizeSettingsCopy(guide.next)}
        </dd>
      </dl>
      {children}
      {actions ? <div className="stg-guide-actions">{actions}</div> : null}
    </div>
  );
}
