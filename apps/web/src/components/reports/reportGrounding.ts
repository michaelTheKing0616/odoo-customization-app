/**
 * PDF-04 — client-side field grounding for the report designer.
 * Mirrors apps/api/app/report_design.py collect/validate gates.
 * Schema rows come from api.listFields (T1-A1 / fields_get path).
 */

import type { FieldRow } from "@/lib/api";
import type { ReportBlock, ReportDesignSpec } from "./ReportCanvas";

export const RELATIONAL_LINE_TYPES = new Set(["one2many", "many2many"]);
export const SPECIAL_IMAGE_SRCS = new Set(["company_logo"]);

export type FieldToken = {
  scope: "parent" | "column";
  field: string;
  o2m_field?: string;
};

export function stripRecordPrefix(field: string, recordVar = "doc"): string {
  const path = (field || "").trim();
  const prefix = `${recordVar}.`;
  return path.startsWith(prefix) ? path.slice(prefix.length) : path;
}

export function collectFieldTokens(blocks: ReportBlock[]): FieldToken[] {
  const tokens: FieldToken[] = [];
  for (const block of blocks) {
    if (block.type === "field" || block.type === "label_field") {
      const name = stripRecordPrefix(block.field || "");
      if (name) tokens.push({ scope: "parent", field: name });
    } else if (block.type === "image") {
      const src = (block.image_src || block.field || "").trim();
      if (src && !SPECIAL_IMAGE_SRCS.has(src)) {
        const name = stripRecordPrefix(src);
        if (name) tokens.push({ scope: "parent", field: name });
      }
    } else if (block.type === "o2m_table") {
      const o2m = stripRecordPrefix(block.o2m_field || block.field || "");
      if (o2m) tokens.push({ scope: "parent", field: o2m });
      for (const col of block.columns || []) {
        const colField = (col.field || "").trim();
        if (colField) {
          tokens.push({ scope: "column", field: colField, o2m_field: o2m || "" });
        }
      }
    }
  }
  return tokens;
}

export function relationalLineFields(rows: FieldRow[]): Map<string, string> {
  const out = new Map<string, string>();
  for (const row of rows) {
    if (RELATIONAL_LINE_TYPES.has(row.ttype) && row.relation) {
      out.set(row.name, row.relation);
    }
  }
  return out;
}

export function parentFieldOptions(rows: FieldRow[]): FieldRow[] {
  return rows.slice().sort((a, b) => a.name.localeCompare(b.name));
}

export function o2mFieldOptions(rows: FieldRow[]): FieldRow[] {
  return rows
    .filter((r) => RELATIONAL_LINE_TYPES.has(r.ttype) && r.relation)
    .sort((a, b) => a.name.localeCompare(b.name));
}

export function refuseEmptyDesign(spec: Pick<ReportDesignSpec, "blocks">): string | null {
  if (!spec.blocks || spec.blocks.length === 0) {
    return "empty design does not create a report";
  }
  return null;
}

export function validateGroundedFields(
  blocks: ReportBlock[],
  parentFields: Set<string> | Iterable<string>,
  relatedFields?: Map<string, Set<string>> | Record<string, Set<string> | string[]>,
): string | null {
  const parent = parentFields instanceof Set ? parentFields : new Set(parentFields);
  const related = new Map<string, Set<string>>();
  if (relatedFields) {
    if (relatedFields instanceof Map) {
      for (const [k, v] of relatedFields) {
        related.set(k, v instanceof Set ? v : new Set(v));
      }
    } else {
      for (const [k, v] of Object.entries(relatedFields)) {
        related.set(k, v instanceof Set ? v : new Set(v));
      }
    }
  }
  for (const token of collectFieldTokens(blocks)) {
    if (token.scope === "parent") {
      if (!parent.has(token.field)) {
        return `unknown field on model: ${token.field}`;
      }
      continue;
    }
    const o2m = token.o2m_field || "";
    const allowed = related.get(o2m);
    if (!allowed) {
      return `unknown related model for line table field '${o2m}'; column '${token.field}' refused`;
    }
    if (!allowed.has(token.field)) {
      return `unknown field on related model for ${o2m}: ${token.field}`;
    }
  }
  return null;
}

/** Default for new primary designs — matches API use_external_layout default. */
export const DEFAULT_USE_EXTERNAL_LAYOUT = true;
