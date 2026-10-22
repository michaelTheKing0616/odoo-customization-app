/**
 * UI-S-26 Bulk data import screen logic and copy.
 * Pure helpers. No React. Test run before commit; what / why / next for empty and error.
 */

import type { DataImportCommitOut, ImageImportCommitOut } from "@/lib/api";

export const PAGE_TITLE = "Bulk data import";
export const PAGE_DESCRIPTION =
  "Upload CSV or XLSX, map columns to Odoo fields, test run the counts, then commit. Writes need the risk phrase.";
export const PRIMARY_CTA = "Commit";
export const DRY_RUN_CTA = "Test run";
export const PARSE_CTA = "Parse file";
export const CONFIRM_PHRASE = "I understand the risks";

export const IMPORT_STEPS = ["Upload", "Map", "Validate", "Commit"] as const;
export type ImportStepLabel = (typeof IMPORT_STEPS)[number];
export type ImportStepIndex = 1 | 2 | 3 | 4;

export type ImportGuide = { title: string; why: string; next: string };

export type ImportErrorContext =
  | "load"
  | "preview"
  | "dry_run"
  | "commit"
  | "template"
  | "image_preview"
  | "image_commit"
  | "seed";

export function importStepFromState(opts: {
  rowCount: number;
  lastResult: DataImportCommitOut | null;
}): ImportStepIndex {
  if (opts.rowCount <= 0) return 1;
  if (!opts.lastResult) return 2;
  if (opts.lastResult.dry_run) return 3;
  return 4;
}

export function emptyImportGuide(): ImportGuide {
  return {
    title: "No file parsed yet",
    why: "Commit needs a CSV or XLSX mapped to an Odoo model, with a test run first so you see create, update, skip, and error counts.",
    next: "Download a template or pick a seed pack, choose a file, then Parse file.",
  };
}

export function seedPacksEmptyGuide(): ImportGuide {
  return {
    title: "No seed packs on this connection",
    why: "Demo packs are optional starter CSVs for common models. This instance has none enabled.",
    next: "Upload your own CSV below, or ask an admin to enable seed packs.",
  };
}

export function mappingEmptyGuide(): ImportGuide {
  return {
    title: "Columns need field names",
    why: "Each CSV column must map to an Odoo field before test run can count creates and updates.",
    next: "Fill the Odoo field for every column you want to write, then run Test run.",
  };
}

export function importErrorGuide(context: ImportErrorContext, rawMessage?: string): ImportGuide {
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
    return null;
  };
  const whyOr = (fallback: string) => classifiedWhy() || fallback;

  switch (context) {
    case "preview":
      return {
        title: "Could not parse the file",
        why: whyOr("The file may be empty, the wrong type, or the API could not read the sheet."),
        next: "Check the file is CSV or XLSX, confirm the target model, then Parse file again.",
      };
    case "dry_run":
      return {
        title: "Test run did not finish",
        why: whyOr("The connection refused the preview write, or a mapped field is invalid."),
        next: "Fix the mapping or match fields, then run Test run again. No rows were written.",
      };
    case "commit":
      return {
        title: "Commit did not finish",
        why: whyOr("The connection refused the write, confirmation failed, or the request timed out."),
        next: "Review the counts and error CSV if present, then retry Commit. Partial writes are not rolled back.",
      };
    case "template":
      return {
        title: "Could not download the template",
        why: whyOr("The API did not return a CSV for this model."),
        next: "Confirm the target model name, then try Download template again.",
      };
    case "image_preview":
      return {
        title: "Image manifest preview failed",
        why: whyOr("The CSV and ZIP must both be present, and the match column must resolve."),
        next: "Check the manifest columns (match, name, filename) and the ZIP paths, then Preview again.",
      };
    case "image_commit":
      return {
        title: "Image commit did not finish",
        why: whyOr("Match field, image field, or confirmation failed on this connection."),
        next: "Fix the match or image field, then retry Commit images. Partial writes are not rolled back.",
      };
    case "seed":
      return {
        title: "Could not load seed packs",
        why: whyOr("The seed pack list did not load from this connection."),
        next: "Reload packs, or skip seeds and upload a CSV instead.",
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

/** Columns mapped to a blank field name. */
export function unmappedColumns(mapping: Record<string, string>, headers: string[]): string[] {
  return headers.filter((h) => !(mapping[h] || "").trim());
}

export function mappingReady(mapping: Record<string, string>, headers: string[]): boolean {
  if (!headers.length) return false;
  return unmappedColumns(mapping, headers).length < headers.length;
}

export function commitBlockedReason(opts: {
  rowCount: number;
  busy: boolean;
  headers: string[];
  mapping: Record<string, string>;
}): string | null {
  if (opts.busy) return null;
  if (opts.rowCount <= 0) return "Parse a CSV or XLSX first.";
  if (!mappingReady(opts.mapping, opts.headers)) {
    return "Map at least one CSV column to an Odoo field.";
  }
  return null;
}

export function dryRunBlockedReason(opts: {
  rowCount: number;
  busy: boolean;
  headers: string[];
  mapping: Record<string, string>;
}): string | null {
  return commitBlockedReason(opts);
}

export type ImportCountStrip = {
  created: number;
  updated: number;
  failed: number;
  skipped: number;
  dryRun: boolean;
  ok: boolean;
  message: string;
  hasErrorCsv: boolean;
};

export function countStripFromResult(
  result: DataImportCommitOut | ImageImportCommitOut,
): ImportCountStrip {
  const created = "created" in result ? result.created : 0;
  return {
    created,
    updated: result.updated,
    failed: result.failed,
    skipped: result.skipped,
    dryRun: "dry_run" in result ? Boolean(result.dry_run) : false,
    ok: result.ok,
    message: result.message,
    hasErrorCsv: "error_csv" in result ? Boolean(result.error_csv) : false,
  };
}

export function resultTone(
  strip: ImportCountStrip,
): "success" | "warning" | "danger" | "info" {
  if (strip.failed > 0 && (strip.created > 0 || strip.updated > 0)) return "warning";
  if (strip.failed > 0) return "danger";
  if (strip.dryRun) return "info";
  return "success";
}

export function partialFailureGuide(strip: ImportCountStrip): ImportGuide | null {
  if (strip.failed <= 0) return null;
  return {
    title: strip.dryRun
      ? `${strip.failed} row(s) would fail`
      : `${strip.failed} row(s) failed on commit`,
    why: strip.dryRun
      ? "Test run found rows that cannot create or update with the current mapping."
      : "Some rows wrote; failed rows were left as reported. Partial success is not rolled back.",
    next: strip.hasErrorCsv
      ? "Download the error CSV, fix those rows, then test run again."
      : "Fix the mapping or source rows, then test run again.",
  };
}

/** Strip em dashes and similar from operator-facing strings. */
export function sanitizeImportCopy(text: string): string {
  return text.replace(/\u2014|\u2013/g, "-").replace(/\s+-\s+/g, " - ");
}

/** Test run honesty folded into the studio bar (kills twin-banner with empty guide). */
export function importHonestyGuide(): ImportGuide {
  return {
    title: "Test run first. Commit writes for real.",
    why: "Parse and map the sheet, then Test run to see create, update, skip, and error counts. Commit needs the risk phrase and writes on this live connection.",
    next: "Map columns, run Test run, read the counts, then Commit only when the strip looks right.",
  };
}

export function importSessionBadge(step: ImportStepIndex): {
  label: string;
  variant: "default" | "warning" | "success" | "info" | "danger";
} {
  if (step === 4) return { label: "Commit", variant: "success" };
  if (step === 3) return { label: "Validate", variant: "info" };
  if (step === 2) return { label: "Map", variant: "warning" };
  return { label: "Upload", variant: "default" };
}

export function importSessionHint(opts: {
  lastResult: DataImportCommitOut | null;
}): string {
  const r = opts.lastResult;
  if (!r) return "Ready on this connection.";
  if (r.dry_run) {
    return "Test run complete. No rows written. Review the counts, then Commit.";
  }
  if (r.failed > 0) {
    return "Commit finished with row errors. Download the error CSV if present.";
  }
  return "Commit applied. Partial success is not rolled back.";
}

