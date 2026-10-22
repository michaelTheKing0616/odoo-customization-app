"use client";

import { reminderScheduleSummary, type ReminderMode } from "@/lib/remindersScreen";

type ReminderSchedulePreviewProps = {
  createCron: boolean;
  mode: ReminderMode;
  intervalNumber: number;
  intervalType: string;
  dueSoonDays: number;
  dateField: string;
};

/** Honesty chip: schedule enabled vs template-only before create. */
export function ReminderSchedulePreview(props: ReminderSchedulePreviewProps) {
  const summary = reminderScheduleSummary(props);
  return (
    <div
      className="rm-schedule"
      data-testid="reminders-schedule-preview"
      data-enabled={summary.enabled ? "true" : "false"}
    >
      <span className="rm-schedule-label">Schedule</span>
      <span className="rm-schedule-value" data-testid="reminders-schedule-headline">
        {summary.headline}
      </span>
      <span className="rm-schedule-detail" data-testid="reminders-schedule-detail">
        {summary.detail}
      </span>
    </div>
  );
}
