/**
 * UI-S-30 Bulk Suite screen logic and copy.
 * Pure helpers. No React. Blast radius before Run; what / why / next for empty and error.
 */

export const PAGE_TITLE = "Bulk Suite";
export const PAGE_DESCRIPTION =
  "Discover form-view workflow buttons per model and run them in bulk. Test run first. Runs as the connected Odoo user. Partial failures are reported per record and are not auto-undone.";
export const PRIMARY_CTA = "Run bulk action";
export const DRY_RUN_CTA = "Test run";
export const DISCOVER_CTA = "Discover transitions";
export const CONFIRM_PHRASE = "I understand the risks";

export const BULK_STEPS = ["Model", "Select", "Test run", "Run"] as const;
export type BulkStepLabel = (typeof BULK_STEPS)[number];
export type BulkStepIndex = 1 | 2 | 3 | 4;

export type BulkGuide = { title: string; why: string; next: string };

export type BulkErrorContext =
  | "load"
  | "discover"
  | "dry_run"
  | "run"
  | "mass_edit"
  | "dedupe"
  | "activities"
  | "security"
  | "portal"
  | "send_message";

export type BulkBlastRadius = {
  label: string;
  detail: string;
  tone: "neutral" | "warning" | "accent" | "danger";
  known: boolean;
  recordCount: number | null;
  modelCount: number;
};

/** Strip em / en dashes from UI copy (playbook §0 law 9). */
export function sanitizeBulkCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function emptyBulkGuide(): BulkGuide {
  return {
    title: "No bulk run yet",
    why: "A write needs a model, a selection (domain or ids), and a test run so you see the blast radius before anything changes.",
    next: "Choose a model, Discover transitions or open a recipe, then Test run before Run bulk action.",
  };
}

export function bulkHonestyGuide(): BulkGuide {
  return {
    title: "Batch writes are not auto-undone",
    why: "Successful rows stay written even when later rows fail. Undo is partial when a snapshot exists.",
    next: "Test run first. Read the blast radius. Confirm with the risk phrase only when the counts look right.",
  };
}

export function partialFailureGuide(opts: {
  total: number;
  succeeded: number;
  failed: number;
  model: string;
}): BulkGuide | null {
  if (opts.failed <= 0) return null;
  return {
    title: `Finished with ${opts.failed} failure${opts.failed === 1 ? "" : "s"}`,
    why: `${opts.succeeded} of ${opts.total} ${opts.model} record${opts.total === 1 ? "" : "s"} succeeded. Failed rows were not rolled back with the successes.`,
    next: "Filter the result table to Failed, fix those records, then retry only the failures.",
  };
}

export function bulkErrorGuide(context: BulkErrorContext, rawMessage?: string): BulkGuide {
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
    if (/not bulk-safe|bulk_safe/.test(m)) {
      return "That transition is marked not bulk-safe on this form view.";
    }
    if (/invalid domain|domain must|invalid values|enter at least one/.test(m)) {
      return "The selection or values JSON did not parse as expected.";
    }
    return null;
  };
  const whyOr = (fallback: string) => classifiedWhy() || fallback;

  switch (context) {
    case "discover":
      return {
        title: "Could not discover transitions",
        why: whyOr("The primary form view for this model did not return object buttons."),
        next: "Confirm the model name, then Discover transitions again.",
      };
    case "dry_run":
      return {
        title: "Test run did not finish",
        why: whyOr("The connection refused the preview, or the selection is invalid."),
        next: "Fix the domain or ids, then Test run again. No records were written.",
      };
    case "run":
      return {
        title: "Bulk action did not finish",
        why: whyOr("The connection refused the write, confirmation failed, or the request timed out."),
        next: "Review per-row results. Successful rows are not auto-undone. Retry only what failed.",
      };
    case "mass_edit":
      return {
        title: "Mass edit did not finish",
        why: whyOr("Field values, protected-module policy, or confirmation blocked the write."),
        next: "Check values JSON and protected fields, Test run, then Apply mass edit again.",
      };
    case "dedupe":
      return {
        title: "Duplicate merge did not finish",
        why: whyOr("Winner selection, FK relink, or confirmation failed on this connection."),
        next: "Pick a winner, Test run merge, then Merge group. Download the merge backup if one exists.",
      };
    case "activities":
      return {
        title: "Bulk activities did not finish",
        why: whyOr("The model may lack mail.activity.mixin, or the activity type is invalid."),
        next: "Probe the model, confirm the activity type and deadline, then Test run.",
      };
    case "security":
      return {
        title: "Security apply did not finish",
        why: whyOr("Group ids, user ids, or confirmation failed. Implied groups are warned, never edited."),
        next: "Preview the diff, Test run apply, then Apply only when the membership change looks right.",
      };
    case "portal":
      return {
        title: "Portal batch did not finish",
        why: whyOr("Partners without email are skipped on grant. Confirmation or rights may have failed."),
        next: "Check partner ids and emails, Test run, then Execute again.",
      };
    case "send_message":
      return {
        title: "Bulk send message did not finish",
        why: whyOr("message_post failed per record, or the template id is invalid."),
        next: "Confirm subject or template, Test run, then Send. This is not mass-mail composer.",
      };
    case "load":
    default:
      return {
        title: "This connection did not load",
        why: whyOr("The Ingenium API or this Odoo connection did not answer in time."),
        next: "Reload the page once the API is up, or open Connect to check the instance.",
      };
  }
}

export function countIds(idsText: string): number {
  return idsText
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => Number(s))
    .filter((n) => Number.isFinite(n) && n > 0).length;
}

export function blastRadiusFromState(opts: {
  model: string;
  selectionMode: "domain" | "ids";
  idsText: string;
  resultTotal?: number | null;
  resultFailed?: number | null;
  dryRunResult?: boolean | null;
  modelsTouched?: number;
}): BulkBlastRadius {
  const model = (opts.model || "").trim() || "model";
  const modelCount = Math.max(1, opts.modelsTouched ?? 1);

  if (typeof opts.resultTotal === "number" && opts.resultTotal >= 0) {
    const failed = opts.resultFailed ?? 0;
    const dry = opts.dryRunResult === true;
    const label = `${opts.resultTotal} record${opts.resultTotal === 1 ? "" : "s"} on ${modelCount} model${modelCount === 1 ? "" : "s"}`;
    const detail = dry
      ? `Test run preview on ${model}. No writes yet.`
      : failed > 0
        ? `Last run wrote with ${failed} failure${failed === 1 ? "" : "s"} on ${model}.`
        : `Last run finished on ${model}.`;
    return {
      label,
      detail,
      tone: failed > 0 ? "danger" : dry ? "accent" : "neutral",
      known: true,
      recordCount: opts.resultTotal,
      modelCount,
    };
  }

  if (opts.selectionMode === "ids") {
    const n = countIds(opts.idsText);
    if (n > 0) {
      return {
        label: `${n} record${n === 1 ? "" : "s"} on ${modelCount} model${modelCount === 1 ? "" : "s"}`,
        detail: `Explicit ids on ${model}. Test run before Run bulk action.`,
        tone: "warning",
        known: true,
        recordCount: n,
        modelCount,
      };
    }
    return {
      label: "Blast radius unknown",
      detail: "Enter at least one record id, or switch to a domain and Test run.",
      tone: "warning",
      known: false,
      recordCount: null,
      modelCount,
    };
  }

  return {
    label: "Blast radius unknown",
    detail: `Domain selection on ${model}. Test run to count matching records before Run bulk action.`,
    tone: "warning",
    known: false,
    recordCount: null,
    modelCount,
  };
}

export function bulkStepFromState(opts: {
  model: string;
  hasSelection: boolean;
  hasDryRun: boolean;
  hasWriteResult: boolean;
}): BulkStepIndex {
  if (!(opts.model || "").trim()) return 1;
  if (!opts.hasSelection) return 2;
  if (!opts.hasDryRun && !opts.hasWriteResult) return 3;
  if (opts.hasWriteResult) return 4;
  return 3;
}

export function runBlockedReason(opts: {
  busy: boolean;
  method: string;
  bulkSafe: boolean | null;
  selectionMode: "domain" | "ids";
  idsText: string;
  domainText: string;
}): string | null {
  if (opts.busy) return null;
  if (!opts.method.trim()) return "Discover transitions and pick a method first.";
  if (opts.bulkSafe === false) return "This transition is not bulk-safe on the form view.";
  if (opts.selectionMode === "ids" && countIds(opts.idsText) === 0) {
    return "Enter at least one numeric record id.";
  }
  if (opts.selectionMode === "domain") {
    try {
      const domain = JSON.parse(opts.domainText) as unknown;
      if (!Array.isArray(domain)) return "Domain must be a JSON list, e.g. [].";
    } catch {
      return "Domain must be valid JSON, e.g. [].";
    }
  }
  return null;
}
