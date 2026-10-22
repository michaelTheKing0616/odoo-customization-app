import type { BulkRunOut } from "@/lib/api";
import type { BulkRunResult } from "@/components/ui/BulkResultTable";

export const CONFIRM_PHRASE = "I understand the risks";

export type BulkConfirmMode =
  | "transition"
  | "mass_edit"
  | "dedupe_merge"
  | "activities"
  | "security"
  | "portal"
  | "send_message";

export const BULK_RECIPES = [
  {
    id: "archive-inactive",
    label: "Archive inactive partners",
    model: "res.partner",
    domain: '[["active","=",false]]',
    op: "archive" as const,
  },
  {
    id: "mass-tag",
    label: "Mass edit partner comment",
    model: "res.partner",
    domain: "[]",
    values: '{"comment": "Bulk update"}',
    op: "mass_edit" as const,
  },
  {
    id: "dedupe-email",
    label: "Dedupe partners by email",
    model: "res.partner",
    domain: "[]",
    op: "dedupe_merge" as const,
  },
] as const;

export type BulkRecipe = (typeof BULK_RECIPES)[number];

export function bulkRunToTable(result: BulkRunOut): BulkRunResult {
  return {
    run_id: result.run_id,
    operation: result.operation,
    model: result.model,
    total: result.total,
    succeeded: result.succeeded,
    failed: result.failed,
    per_record: result.per_record.map((r) => ({
      record_id: r.id,
      display_name: r.display_name,
      ok: r.ok,
      error: r.error,
    })),
    dry_run: result.dry_run,
    message: result.message,
    status: result.status,
    pending_ids: result.pending_ids,
    processed_count: result.processed_count,
    aborted: result.aborted,
    can_continue: result.can_continue,
  };
}

export function parseSelection(
  selectionMode: "domain" | "ids",
  domainText: string,
  idsText: string,
): { domain?: unknown[]; ids?: number[] } {
  if (selectionMode === "domain") {
    try {
      const domain = JSON.parse(domainText) as unknown[];
      if (!Array.isArray(domain)) throw new Error("domain must be a list");
      return { domain };
    } catch {
      throw new Error("Invalid domain JSON - use Odoo domain list, e.g. []");
    }
  }
  const ids = idsText
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => Number(s))
    .filter((n) => Number.isFinite(n) && n > 0);
  if (!ids.length) throw new Error("Enter at least one numeric record id");
  return { ids };
}

export function parseIdList(text: string, label: string): number[] {
  const ids = text
    .split(/[\s,]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => Number(s))
    .filter((n) => Number.isFinite(n) && n > 0);
  if (!ids.length) throw new Error(`Enter at least one ${label} id`);
  return ids;
}
