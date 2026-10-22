/**
 * UI-S-34 Reminders screen logic and copy.
 * Pure helpers. No React. Honesty for schedule enable vs template-only.
 * One teal primary: Create the reminder.
 */

export const PAGE_TITLE = "Reminders";
export const PAGE_DESCRIPTION =
  "Build a date-driven mail.template and optionally an active ir.cron that emails matching records. Writes need the risk phrase. No raw XML.";
export const PRIMARY_CTA = "Create the reminder";
export const CONFIRM_PHRASE = "I understand the risks";

export const REMINDER_STEPS = ["Compose", "Schedule", "Confirm", "Created"] as const;
export type ReminderStepLabel = (typeof REMINDER_STEPS)[number];
export type ReminderStepId = "compose" | "schedule" | "confirm" | "created";

export type ReminderGuide = { title: string; why: string; next: string };

export type ReminderMode = "overdue" | "due_soon";
export type ReminderIntervalType = "minutes" | "hours" | "days" | "weeks" | "months";

export type ReminderErrorContext =
  | "load"
  | "validate"
  | "create"
  | "confirm";

/** Strip em / en dashes from UI copy (playbook law 9). */
export function sanitizeReminderCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function resolveReminderStep(opts: {
  hasResult: boolean;
  confirmOpen: boolean;
  scheduleTouched: boolean;
  composing: boolean;
}): ReminderStepId {
  if (opts.hasResult) return "created";
  if (opts.confirmOpen) return "confirm";
  if (opts.scheduleTouched) return "schedule";
  return "compose";
}

export function emptyReminderGuide(): ReminderGuide {
  return {
    title: "No reminder created yet",
    why: "A mail.template keyed to a date field, plus an optional active cron, so overdue or due-soon records get emailed on a schedule you control.",
    next: "Fill name, model, and date field. Choose schedule on or off. Then Create the reminder.",
  };
}

/** Always-on honesty: schedule enable vs template-only. */
export function reminderHonestyGuide(createCron: boolean): ReminderGuide {
  if (createCron) {
    return {
      title: "Schedule will be enabled on create",
      why: "Create writes a mail.template and an active ir.cron. The cron searches by the date field and queues the template on every interval. Outgoing mail depends on Odoo mail config.",
      next: "Review interval and email_to, then Create the reminder. The risk phrase is required before the live write.",
    };
  }
  return {
    title: "Template only. Schedule stays off",
    why: "Create writes a mail.template only. No ir.cron. Nothing sends automatically until you schedule it in Cron Manager or Odoo.",
    next: "Turn on Create cron below if you want an active schedule, or Create the reminder as template-only.",
  };
}

export function reminderScheduleSummary(opts: {
  createCron: boolean;
  mode: ReminderMode;
  intervalNumber: number;
  intervalType: ReminderIntervalType | string;
  dueSoonDays: number;
  dateField: string;
}): { headline: string; detail: string; enabled: boolean } {
  const n = Math.max(1, Math.floor(Number(opts.intervalNumber) || 1));
  const unit = n === 1 ? String(opts.intervalType).replace(/s$/, "") : String(opts.intervalType);
  const modeLabel =
    opts.mode === "overdue"
      ? `records where ${opts.dateField || "date field"} is before today`
      : `records due within ${Math.max(1, opts.dueSoonDays)} day(s) on ${opts.dateField || "date field"}`;

  if (!opts.createCron) {
    return {
      headline: "Schedule off",
      detail: `Template only for ${modeLabel}. No automatic sends.`,
      enabled: false,
    };
  }
  return {
    headline: "Schedule enabled",
    detail: `Active cron every ${n} ${unit} for ${modeLabel}.`,
    enabled: true,
  };
}

export function reminderCreatedGuide(opts: {
  mailTemplateId: number | null;
  cronId: number | null;
}): ReminderGuide {
  if (opts.cronId != null) {
    return {
      title: "Reminder created with schedule enabled",
      why: `Template ${opts.mailTemplateId ?? "?"} and cron ${opts.cronId} are live on Odoo. The cron is active and will queue mail on its interval.`,
      next: "Open Cron Manager to pause, tune interval, or Run now. Check Odoo outgoing mail if messages stay queued.",
    };
  }
  return {
    title: "Template created. Schedule stayed off",
    why: `mail.template ${opts.mailTemplateId ?? "?"} is on Odoo. No ir.cron was created, so nothing sends on a schedule yet.`,
    next: "Create again with Create cron on, or schedule the template from Cron Manager.",
  };
}

export function reminderErrorGuide(
  context: ReminderErrorContext,
  detail?: string | null,
): ReminderGuide {
  const m = (detail || "").toLowerCase();
  const classifiedWhy = (): string | null => {
    if (/\b40[13]\b|permission|access denied|not allowed|forbidden/.test(m)) {
      return "The Odoo user on this connection lacks the rights for that step.";
    }
    if (/confirm|phrase|i understand the risks/.test(m)) {
      return "This write needs the risk phrase before it can continue.";
    }
    if (/model .+ not found|field .+ not found/.test(m)) {
      return "The model or date field is missing on this database.";
    }
    if (/mail/.test(m) && /module|install/.test(m)) {
      return "The mail module is missing or could not be ensured on this database.";
    }
    if (/mutation|read.only|blocked/.test(m)) {
      return "Advanced mutations are blocked on this connection.";
    }
    return null;
  };
  const whyOr = (fallback: string) => classifiedWhy() || fallback;
  const titleBy: Record<ReminderErrorContext, string> = {
    load: "Could not load Reminders",
    validate: "Form needs a fix before create",
    create: "Could not create the reminder",
    confirm: "Confirmation required",
  };
  const nextBy: Record<ReminderErrorContext, string> = {
    load: "Check the connection, then open Reminders again.",
    validate: "Fix name, model, and date field, then try Create the reminder again.",
    create: "Fix the reported field or rights, then Create the reminder again with the risk phrase.",
    confirm: "Type the risk phrase exactly, then confirm.",
  };
  return {
    title: titleBy[context],
    why: whyOr(detail || "The server returned an error for this step."),
    next: nextBy[context],
  };
}

export function intervalLabel(number: number, type: ReminderIntervalType | string): string {
  const n = Math.max(1, Math.floor(Number(number) || 1));
  const unit = n === 1 ? String(type).replace(/s$/, "") : String(type);
  return `Every ${n} ${unit}`;
}

export function canSubmitReminder(opts: {
  name: string;
  model: string;
  dateField: string;
  canCreate: boolean;
}): boolean {
  return (
    opts.canCreate &&
    opts.name.trim().length > 0 &&
    opts.model.trim().length > 0 &&
    opts.dateField.trim().length > 0
  );
}
