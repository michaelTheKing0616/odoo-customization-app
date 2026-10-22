/**
 * UI-S-27 ID Generator screen logic and copy.
 * Pure helpers. No React. Preview / CSV download never write Odoo;
 * live test run lists proposed codes; Apply writes; ir.sequence is optional and separate.
 */

export const PAGE_TITLE = "ID Generator";
export const PAGE_DESCRIPTION =
  "Build reference codes as Prefix / Initials / Number (for example INV-AO-0001) from names. Preview and CSV download never write Odoo. Live test run lists proposed codes; Apply writes with the risk phrase.";
export const PRIMARY_CTA = "Download updated CSV";
export const PREVIEW_CTA = "Preview CSV";
export const DRY_RUN_CTA = "Test run live";
export const APPLY_CTA = "Apply codes";
export const SEQUENCE_CTA = "Create sequence bridge";
export const CONFIRM_PHRASE = "I understand the risks";

export const IDGEN_STEPS = ["Source", "Rules", "Preview", "Deliver"] as const;
export type IdGenStepLabel = (typeof IDGEN_STEPS)[number];
export type IdGenStepIndex = 1 | 2 | 3 | 4;
export type IdGenMode = "csv" | "live";

export type IdGenGuide = { title: string; why: string; next: string };

export type IdGenErrorContext =
  | "load"
  | "csv_preview"
  | "csv_download"
  | "live_dry_run"
  | "live_apply"
  | "sequence";

/** Strip em / en dashes from UI copy (playbook law 9). */
export function sanitizeIdGenCopy(text: string): string {
  return text.replace(/[\u2014\u2013]/g, "-");
}

export function emptyCellDisplay(value: string | null | undefined): string {
  const v = (value ?? "").trim();
  return v.length ? v : "none";
}

export function idGenStepFromState(opts: {
  mode: IdGenMode;
  hasSource: boolean;
  hasPreview: boolean;
  delivered: boolean;
}): IdGenStepIndex {
  if (opts.delivered) return 4;
  if (opts.hasPreview) return 3;
  if (opts.hasSource) return 2;
  return 1;
}

export function emptyIdGenGuide(mode: IdGenMode): IdGenGuide {
  if (mode === "csv") {
    return {
      title: "No spreadsheet preview yet",
      why: "Download needs a CSV or XLSX with names, plus a preview so you see old and new codes before saving a file.",
      next: "Choose a file, set the name column and prefix rules, then Preview CSV.",
    };
  }
  return {
    title: "No live test run yet",
    why: "Apply writes codes on live records. A test run lists proposed codes with no writes so you can check collisions first.",
    next: "Set the model and fields, then Test run live before Apply codes.",
  };
}

export function idGenHonestyGuide(): IdGenGuide {
  return {
    title: "Preview and CSV download never write Odoo",
    why: "Live test run only lists proposed codes. Apply writes empty code fields when skip-if-present is on. Creating an ir.sequence bridge is a separate optional write after Apply.",
    next: "Preview or Test run first. Download the CSV for offline work, or Apply with the risk phrase only when the preview looks right.",
  };
}

export function sequenceHonestyGuide(enabled: boolean): IdGenGuide {
  if (!enabled) {
    return {
      title: "Sequence bridge is off",
      why: "Codes come from the Prefix / Initials / Number rules on this screen, not from ir.sequence.",
      next: "Leave this off unless you also need an ir.sequence record for future Odoo numbering.",
    };
  }
  return {
    title: "Sequence bridge runs after Apply",
    why: "Checking this creates or updates an ir.sequence after a successful live Apply. It does not change the preview table and is not part of CSV download.",
    next: "Test run and Apply codes first. The bridge write uses the same prefix rules as this run.",
  };
}

export function previewCountsGuide(opts: {
  total: number;
  changed: number;
  skipped: number;
  dryRun?: boolean;
  mode: IdGenMode;
}): IdGenGuide {
  const verb = opts.mode === "csv" ? "CSV preview" : opts.dryRun === false ? "Live apply" : "Live dry-run";
  return {
    title: `${verb}: ${opts.changed} change${opts.changed === 1 ? "" : "s"} of ${opts.total}`,
    why: `${opts.skipped} row${opts.skipped === 1 ? "" : "s"} skipped (already coded or filtered). ${
      opts.mode === "csv" || opts.dryRun !== false
        ? "Nothing was written to Odoo."
        : "Changed rows were written on the live model."
    }`,
    next:
      opts.mode === "csv"
        ? "Download updated CSV when the new codes look right."
        : opts.dryRun === false
          ? "Review failed rows if any. Optionally create the ir.sequence bridge."
          : "Apply codes with the risk phrase only when the proposed codes look right.",
  };
}

export function idGenErrorGuide(context: IdGenErrorContext, rawMessage?: string): IdGenGuide {
  const detail = sanitizeIdGenCopy((rawMessage || "").trim());
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
    if (/confirm|phrase|risk/.test(m)) {
      return "Live Apply needs the exact risk phrase before any write.";
    }
    return null;
  };
  const whyOr = (fallback: string) => classifiedWhy() || fallback;
  const detailSuffix = detail ? ` Detail: ${detail}` : "";

  switch (context) {
    case "csv_preview":
      return {
        title: "Could not preview the spreadsheet",
        why: whyOr("The file may be empty, the wrong type, or the name column is missing.") + detailSuffix,
        next: "Check the file is CSV or XLSX, confirm the name column, then Preview CSV again.",
      };
    case "csv_download":
      return {
        title: "Could not download the updated CSV",
        why: whyOr("Preview rows are missing, or the API could not build the file.") + detailSuffix,
        next: "Run Preview CSV again, then Download updated CSV.",
      };
    case "live_dry_run":
      return {
        title: "Live test run did not finish",
        why: whyOr("The model or fields may be wrong, or the connection refused the read.") + detailSuffix,
        next: "Fix the model and field names, then Test run live again. No codes were written.",
      };
    case "live_apply":
      return {
        title: "Apply did not finish",
        why: whyOr("The connection refused the write, confirmation failed, or the request timed out.") + detailSuffix,
        next: "Review the preview, confirm with the risk phrase, then retry Apply codes. Partial writes are not rolled back.",
      };
    case "sequence":
      return {
        title: "Sequence bridge did not finish",
        why: whyOr("Codes may already be applied, but ir.sequence create/update failed.") + detailSuffix,
        next: "Retry Create sequence bridge, or create the sequence in Odoo Settings manually.",
      };
    case "load":
    default:
      return {
        title: "Could not load this connection",
        why: whyOr("The connection record is missing or the API did not answer.") + detailSuffix,
        next: "Refresh the page or reopen the connection, then try again.",
      };
  }
}

export function downloadBlockedReason(opts: {
  mode: IdGenMode;
  hasCsvPreview: boolean;
  busy: boolean;
}): string | null {
  if (opts.busy) return "Wait for the current step to finish.";
  if (opts.mode !== "csv") return "Switch to CSV to download an updated spreadsheet.";
  if (!opts.hasCsvPreview) return "Preview CSV first so the download includes new codes.";
  return null;
}

export function applyBlockedReason(opts: {
  mode: IdGenMode;
  busy: boolean;
  hasDryRun: boolean;
}): string | null {
  if (opts.busy) return "Wait for the current step to finish.";
  if (opts.mode !== "live") return "Switch to Live to apply codes on Odoo records.";
  if (!opts.hasDryRun) return "Test run live first so you see proposed codes before writing.";
  return null;
}

export function formatCodeExample(opts: {
  prefix: string;
  separator: string;
  padding: number;
  initialsLength: number;
  name?: string;
}): string {
  const prefix = (opts.prefix || "INV").toUpperCase();
  const sep = opts.separator ?? "-";
  const pad = Math.max(1, Math.min(12, Number(opts.padding) || 4));
  const len = Math.max(1, Math.min(8, Number(opts.initialsLength) || 3));
  const name = opts.name || "Acme Trading Co";
  const letters = name
    .replace(/[^A-Za-z\s]/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0]!.toUpperCase())
    .join("")
    .slice(0, len)
    .padEnd(len, "X");
  const num = String(1).padStart(pad, "0");
  return `${prefix}${sep}${letters}${sep}${num}`;
}

export function idGenSessionBadge(step: IdGenStepIndex): {
  label: string;
  variant: "default" | "warning" | "success" | "info" | "danger";
} {
  const labels = ["Source", "Rules", "Preview", "Deliver"] as const;
  const i = Math.max(1, Math.min(4, step)) - 1;
  const variants = ["default", "info", "warning", "success"] as const;
  return { label: labels[i], variant: variants[i] };
}

/** Alias used by the IdGeneratorStateGuide component. */
export type IdGeneratorStateGuide = IdGenGuide;
