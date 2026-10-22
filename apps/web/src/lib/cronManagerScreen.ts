/**
 * UI-S-32 Cron Manager screen logic and copy.
 * Pure helpers. No React. Honesty for enable / disable / trigger.
 * One teal primary: Save the cron. Next-run preview in connection timezone.
 */

export const PAGE_TITLE = "Cron Manager";
export const PAGE_DESCRIPTION =
  "Inspect, toggle, trigger, and create scheduled actions that call existing model methods only. No raw Python editor. Test run before Run now. Writes need the risk phrase.";
export const PRIMARY_CTA = "Save the cron";
export const DRY_RUN_CTA = "Test run";
export const RUN_NOW_CTA = "Run now";
export const ENABLE_CTA = "Enable";
export const DISABLE_CTA = "Disable";
export const CONFIRM_PHRASE = "I understand the risks";

export const CRON_STEPS = ["List", "Select", "Trigger", "Save"] as const;
export type CronStepLabel = (typeof CRON_STEPS)[number];
export type CronStepId = "list" | "select" | "trigger" | "save";

export type CronGuide = { title: string; why: string; next: string };

export type CronErrorContext =
  | "load"
  | "refresh"
  | "discover"
  | "dry_run"
  | "run_now"
  | "create"
  | "enable"
  | "disable";

export type CronIntervalType = "minutes" | "hours" | "days" | "weeks" | "months";

export type CronTimeZoneResolve = {
  timeZone: string;
  source: "connection" | "utc";
  label: string;
};

/** Strip em / en dashes from UI copy (playbook law 9). */
export function sanitizeCronCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function resolveCronTimeZone(probe?: Record<string, unknown> | null): CronTimeZoneResolve {
  const raw =
    (typeof probe?.tz === "string" && probe.tz) ||
    (typeof probe?.timezone === "string" && probe.timezone) ||
    (typeof probe?.user_tz === "string" && probe.user_tz) ||
    "";
  const tz = raw.trim();
  if (tz) {
    return {
      timeZone: tz,
      source: "connection",
      label: tz,
    };
  }
  return {
    timeZone: "UTC",
    source: "utc",
    label: "UTC (connection tz not reported)",
  };
}

function parseOdooDateTime(value: string): Date | null {
  const trimmed = value.trim();
  if (!trimmed) return null;
  // Odoo often returns "YYYY-MM-DD HH:mm:ss" naive. Treat as UTC wall time.
  const normalized = /T/.test(trimmed)
    ? trimmed
    : trimmed.replace(" ", "T") + (trimmed.endsWith("Z") || /[+-]\d{2}:?\d{2}$/.test(trimmed) ? "" : "Z");
  const d = new Date(normalized);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function formatCronNextRun(
  nextcall: string | null | undefined,
  timeZone: string,
  opts?: { missingLabel?: string },
): string {
  if (!nextcall) return opts?.missingLabel ?? "No next run scheduled";
  const d = parseOdooDateTime(nextcall);
  if (!d) return sanitizeCronCopy(nextcall);
  try {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone,
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZoneName: "short",
    }).format(d);
  } catch {
    return sanitizeCronCopy(nextcall);
  }
}

export function previewNextRunFromInterval(
  intervalNumber: number,
  intervalType: CronIntervalType,
  timeZone: string,
  now: Date = new Date(),
): Date {
  const n = Math.max(1, Math.floor(Number(intervalNumber) || 1));
  const d = new Date(now.getTime());
  switch (intervalType) {
    case "minutes":
      d.setUTCMinutes(d.getUTCMinutes() + n);
      break;
    case "hours":
      d.setUTCHours(d.getUTCHours() + n);
      break;
    case "days":
      d.setUTCDate(d.getUTCDate() + n);
      break;
    case "weeks":
      d.setUTCDate(d.getUTCDate() + n * 7);
      break;
    case "months": {
      const month = d.getUTCMonth() + n;
      d.setUTCMonth(month);
      break;
    }
    default:
      d.setUTCDate(d.getUTCDate() + n);
  }
  // Touch timeZone validity without changing the instant.
  try {
    new Intl.DateTimeFormat("en-GB", { timeZone }).format(d);
  } catch {
    /* keep UTC date */
  }
  return d;
}

export function formatPreviewNextRun(
  intervalNumber: number,
  intervalType: CronIntervalType,
  timeZone: string,
  now?: Date,
): string {
  const d = previewNextRunFromInterval(intervalNumber, intervalType, timeZone, now);
  try {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone,
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZoneName: "short",
    }).format(d);
  } catch {
    return d.toISOString();
  }
}

export function resolveCronStep(opts: {
  listHydrated: boolean;
  selectedCount: number;
  hasTriggerResult: boolean;
  composing: boolean;
}): CronStepId {
  if (opts.composing) return "save";
  if (opts.hasTriggerResult) return "trigger";
  if (opts.selectedCount > 0) return "select";
  return "list";
}

export function emptyCronGuide(): CronGuide {
  return {
    title: "No scheduled actions match",
    why: "The filter may be too tight, or this connection has no ir.cron rows Ingenium can list yet.",
    next: "Broaden search or status, Refresh the list, or fill Save the cron below to schedule an existing model method.",
  };
}

export function cronHonestyGuide(): CronGuide {
  return {
    title: "Enable, disable, and trigger are live on this database",
    why: "Enable resumes the schedule at nextcall. Disable stops future runs. Run now executes the job immediately as the connected Odoo user. Test run never writes.",
    next: "Test run selected jobs first. Confirm disable and Run now with the risk phrase only when the targets look right.",
  };
}

export function cronErrorGuide(context: CronErrorContext, rawMessage?: string): CronGuide {
  const detail = (rawMessage || "").trim();
  const m = detail.toLowerCase();
  const classifiedWhy = (): string | null => {
    if (/timed? ?out|timeout|took too long|\b50[34]\b/.test(m)) {
      return "The Ingenium API or this Odoo connection took too long to answer.";
    }
    if (/failed to fetch|network|econn|unreachable|could not reach|offline/.test(m)) {
      return "Ingenium could not reach its API or this Odoo connection.";
    }
    if (/\b40[13]\b|permission|access denied|not allowed|forbidden/.test(m)) {
      return "The Odoo user on this connection lacks the rights for that step.";
    }
    if (/confirm|phrase|i understand the risks/.test(m)) {
      return "This write needs the risk phrase before it can continue.";
    }
    if (/select at least one|no scheduled action/.test(m)) {
      return "A trigger needs one or more selected scheduled actions.";
    }
    if (/name, model, and method|required/.test(m)) {
      return "Save the cron needs a name, model, and public method.";
    }
    return null;
  };
  const whyOr = (fallback: string) => classifiedWhy() || fallback;
  const titleBy: Record<CronErrorContext, string> = {
    load: "Could not load Cron Manager",
    refresh: "Could not refresh scheduled actions",
    discover: "Could not discover form methods",
    dry_run: "Test run failed",
    run_now: "Run now failed",
    create: "Could not save the cron",
    enable: "Could not enable the schedule",
    disable: "Could not disable the schedule",
  };
  const nextBy: Record<CronErrorContext, string> = {
    load: "Check the connection, then open Cron Manager again.",
    refresh: "Wait a moment, then Refresh the list.",
    discover: "Confirm the model name, or type a known public method such as action_confirm.",
    dry_run: "Confirm the selection, then Test run again before Run now.",
    run_now: "Test run again, fix failing jobs, then retry Run now with the risk phrase.",
    create: "Fix name, model, and method, then Save the cron again.",
    enable: "Refresh the list, then try Enable again.",
    disable: "Refresh the list, then Disable again with the risk phrase.",
  };
  return {
    title: titleBy[context],
    why: whyOr(detail || "The server returned an error for this step."),
    next: nextBy[context],
  };
}

export function intervalLabel(number: number, type: CronIntervalType): string {
  const n = Math.max(1, Math.floor(Number(number) || 1));
  const unit = n === 1 ? type.replace(/s$/, "") : type;
  return `Every ${n} ${unit}`;
}
