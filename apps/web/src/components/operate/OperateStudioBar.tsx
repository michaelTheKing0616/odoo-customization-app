"use client";

import type { ReactNode } from "react";
import { Badge } from "@/components/ui/Badge";

export type OperateStudioBarTone = "warning" | "neutral" | "accent" | "danger";

export type OperateStudioBarProps = {
  /** Root + title/why/next test ids: `${testId}`, `${testId}-title`, … */
  testId: string;
  title: string;
  why: string;
  next?: string;
  tone?: OperateStudioBarTone;
  /** Short badge label. Default Caution for warning, Honesty otherwise. */
  badge?: string;
  actions?: ReactNode;
  className?: string;
};

const BADGE_VARIANT: Record<
  OperateStudioBarTone,
  "warning" | "default" | "info" | "danger"
> = {
  warning: "warning",
  neutral: "default",
  accent: "info",
  danger: "danger",
};

/**
 * Compact Studio session bar for Operate desks.
 * Collapses the old twin always-on honesty + guide Callouts into one dense bar
 * (DesignerSessionBar craft: badge + hint + optional next/actions).
 */
export function OperateStudioBar({
  testId,
  title,
  why,
  next,
  tone = "warning",
  badge,
  actions,
  className,
}: OperateStudioBarProps) {
  const badgeLabel =
    badge ?? (tone === "warning" ? "Caution" : tone === "danger" ? "Risk" : "Honesty");

  return (
    <div
      className={["operate-studio-bar", className].filter(Boolean).join(" ")}
      data-tone={tone}
      data-testid={testId}
      role="note"
    >
      <span className="operate-studio-bar-badge" data-testid={`${testId}-badge`}>
        <Badge variant={BADGE_VARIANT[tone]}>{badgeLabel}</Badge>
      </span>
      <div className="operate-studio-bar-copy">
        <p className="operate-studio-bar-title" data-testid={`${testId}-title`}>
          {title}
        </p>
        <p className="operate-studio-bar-why" data-testid={`${testId}-why`}>
          {why}
        </p>
        {next ? (
          <p className="operate-studio-bar-next" data-testid={`${testId}-next`}>
            <span className="operate-studio-bar-next-label">Next</span> {next}
          </p>
        ) : null}
      </div>
      {actions ? <div className="operate-studio-bar-actions">{actions}</div> : null}
    </div>
  );
}
