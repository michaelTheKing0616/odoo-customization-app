"use client";

import type { ReactNode } from "react";
import type { ConnectGuide } from "@/lib/connectScreen";
import { sanitizeConnectCopy } from "@/lib/connectScreen";

type ConnectStateGuideProps = {
  guide: ConnectGuide;
  tone?: "neutral" | "danger" | "success";
  actions?: ReactNode;
  testId?: string;
  live?: boolean;
  className?: string;
  children?: ReactNode;
};

/** Dense state panel for error / success only. Not an always-on banner. */
export function ConnectStateGuide({
  guide,
  tone = "neutral",
  actions,
  testId,
  live = false,
  className,
  children,
}: ConnectStateGuideProps) {
  return (
    <div
      className={["cn-panel-state", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role={live ? "alert" : undefined}
    >
      <p
        className="cn-panel-state-title"
        data-testid={testId ? `${testId}-title` : undefined}
      >
        {sanitizeConnectCopy(guide.title)}
      </p>
      <p
        className="cn-panel-state-body"
        data-testid={testId ? `${testId}-why` : undefined}
      >
        {sanitizeConnectCopy(guide.why)}
      </p>
      <p
        className="cn-panel-state-next"
        data-testid={testId ? `${testId}-next` : undefined}
      >
        <strong>Next.</strong> {sanitizeConnectCopy(guide.next)}
      </p>
      {children}
      {actions ? <div className="cn-success-actions">{actions}</div> : null}
    </div>
  );
}
