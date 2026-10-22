"use client";

import type { ComponentProps, ReactNode } from "react";
import { Badge } from "@/components/ui/Badge";
import {
  sanitizeReminderCopy,
  type ReminderGuide,
  type ReminderStepId,
} from "@/lib/remindersScreen";

type BadgeVariant = NonNullable<ComponentProps<typeof Badge>["variant"]>;

const STEP_BADGE: Record<
  ReminderStepId,
  { label: string; variant: BadgeVariant }
> = {
  compose: { label: "Draft", variant: "default" },
  schedule: { label: "Scheduling", variant: "info" },
  confirm: { label: "Confirm", variant: "warning" },
  created: { label: "Created", variant: "success" },
};

type ReminderStudioBarProps = {
  step: ReminderStepId;
  /** Honesty guide folded into the bar (kills twin-banner). */
  honesty?: ReminderGuide | null;
  /** Optional trailing actions (primary stays in the paper form). */
  actions?: ReactNode;
};

/**
 * Studio-bar chrome for Reminders (UI-S-34 leap).
 * Eyes on Designer session bar + App Studio density: badge + one honesty hint,
 * no second banner card stacked under the rail.
 */
export function ReminderStudioBar({ step, honesty, actions }: ReminderStudioBarProps) {
  const badge = STEP_BADGE[step];
  return (
    <div className="rm-studio-bar" data-testid="reminders-studio-bar">
      <span data-testid="reminders-session-state" className="rm-studio-badge">
        <Badge variant={badge.variant}>{badge.label}</Badge>
      </span>
      {honesty ? (
        <div
          className="rm-studio-honesty"
          data-testid="reminders-honesty"
          data-tone="warning"
        >
          <p
            className="rm-studio-honesty-title"
            data-testid="reminders-honesty-title"
          >
            {sanitizeReminderCopy(honesty.title)}
          </p>
          <p
            className="rm-studio-honesty-why"
            data-testid="reminders-honesty-why"
          >
            {sanitizeReminderCopy(honesty.why)}
          </p>
          <p
            className="rm-studio-honesty-next"
            data-testid="reminders-honesty-next"
          >
            <span className="rm-studio-k">Next</span>{" "}
            {sanitizeReminderCopy(honesty.next)}
          </p>
        </div>
      ) : (
        <p className="rm-studio-hint" data-testid="reminders-session-hint">
          Reminder is on Odoo. Schedule state is locked to what you created.
        </p>
      )}
      {actions ? <div className="rm-studio-actions">{actions}</div> : null}
    </div>
  );
}
