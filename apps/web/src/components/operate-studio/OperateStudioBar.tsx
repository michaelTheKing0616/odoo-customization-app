"use client";

import type { ComponentProps, ReactNode } from "react";
import { Badge } from "@/components/ui/Badge";

type BadgeVariant = NonNullable<ComponentProps<typeof Badge>["variant"]>;

export type OperateGuide = { title: string; why: string; next: string };

export type OperateSessionBadge = {
  label: string;
  variant?: BadgeVariant;
};

type OperateStudioBarProps = {
  badge: OperateSessionBadge;
  /** Honesty folded into the bar (kills twin-banner). */
  honesty?: OperateGuide | null;
  /** Fallback hint when honesty is absent (e.g. terminal success). */
  hint?: string;
  /** Prefix for data-testid roots, e.g. "script-runner". */
  testIdPrefix: string;
  sanitize?: (text: string) => string;
  actions?: ReactNode;
};

const identity = (t: string) => t;

/**
 * Shared Studio-bar for Operate leaps (UI-S-34+).
 * Badge + one honesty strip on basalt; no second stacked guide card.
 */
export function OperateStudioBar({
  badge,
  honesty,
  hint = "Ready on this connection.",
  testIdPrefix,
  sanitize = identity,
  actions,
}: OperateStudioBarProps) {
  return (
    <div className="op-studio-bar" data-testid={`${testIdPrefix}-studio-bar`}>
      <span data-testid={`${testIdPrefix}-session-state`} className="op-studio-badge">
        <Badge variant={badge.variant ?? "default"}>{badge.label}</Badge>
      </span>
      {honesty ? (
        <div
          className="op-studio-honesty"
          data-testid={`${testIdPrefix}-honesty`}
          data-tone="warning"
        >
          <p
            className="op-studio-honesty-title"
            data-testid={`${testIdPrefix}-honesty-title`}
          >
            {sanitize(honesty.title)}
          </p>
          <p
            className="op-studio-honesty-why"
            data-testid={`${testIdPrefix}-honesty-why`}
          >
            {sanitize(honesty.why)}
          </p>
          <p
            className="op-studio-honesty-next"
            data-testid={`${testIdPrefix}-honesty-next`}
          >
            <span className="op-studio-k">Next</span> {sanitize(honesty.next)}
          </p>
        </div>
      ) : (
        <p className="op-studio-hint" data-testid={`${testIdPrefix}-session-hint`}>
          {sanitize(hint)}
        </p>
      )}
      {actions ? <div className="op-studio-actions">{actions}</div> : null}
    </div>
  );
}
