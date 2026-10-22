/**
 * PDF-07 — Table Inspector column model for `o2m_table` blocks.
 * Mirrors apps/api/app/report_design.py (resolve_column_align /
 * parse_column_width / resolve_column_widths / emit_o2m_table). Keep in sync.
 *
 * Grounding: presentation keys (align / width / sum / totals) never add field
 * tokens. Totals may only sum numeric related fields (integer/float/monetary).
 * Width is parsed to a number — user strings never reach a style attribute.
 */

import type { FieldRow } from "@/lib/api";

export type TableAlign = "left" | "center" | "right";
export type TableWidthMode = "auto" | "pct" | "fr";

export type ReportTableColumn = {
  field: string;
  label: string;
  /** Default left; right when `ttype` is numeric. */
  align?: TableAlign;
  /** Number (percent), "25%", or "2fr" (shares what fixed % leave). */
  width?: number | string;
  /** Totals row sums this column (numeric fields only). */
  sum?: boolean;
  /** fields_get type hint; the API re-annotates it from schema on grounding. */
  ttype?: string;
};

export type TableBlockLike = {
  type: string;
  o2m_field?: string;
  field?: string;
  columns?: ReportTableColumn[];
  totals_row?: boolean;
  totals_label?: string;
};

export const TABLE_ALIGNS: readonly TableAlign[] = ["left", "center", "right"];
export const NUMERIC_FIELD_TYPES = new Set(["integer", "float", "monetary"]);
export const DEFAULT_TOTALS_LABEL = "Total";
export const DEFAULT_TABLE_COLUMN: ReportTableColumn = {
  field: "display_name",
  label: "Line",
};

const WIDTH_PCT_RE = /^(\d{1,3}(?:\.\d{1,4})?)\s*%?$/;
const WIDTH_FR_RE = /^(\d{1,3}(?:\.\d{1,4})?)\s*fr$/;

export function isNumericFieldType(ttype?: string | null): boolean {
  return NUMERIC_FIELD_TYPES.has(String(ttype || "").trim().toLowerCase());
}

export function columnDefaultAlign(ttype?: string | null): TableAlign {
  return isNumericFieldType(ttype) ? "right" : "left";
}

export function isTableAlign(value: unknown): value is TableAlign {
  return typeof value === "string" && (TABLE_ALIGNS as readonly string[]).includes(value);
}

export function resolveColumnAlign(column: Partial<ReportTableColumn>): TableAlign {
  const raw = typeof column.align === "string" ? column.align.trim().toLowerCase() : "";
  if (isTableAlign(raw)) return raw;
  return columnDefaultAlign(column.ttype);
}

export type ParsedWidth = { unit: "pct" | "fr"; value: number };

export function parseColumnWidth(raw: unknown): ParsedWidth | null {
  if (raw === null || raw === undefined || typeof raw === "boolean") return null;
  let unit: "pct" | "fr";
  let value: number;
  if (typeof raw === "number") {
    unit = "pct";
    value = raw;
  } else if (typeof raw === "string") {
    const text = raw.trim().toLowerCase();
    if (!text) return null;
    const fr = WIDTH_FR_RE.exec(text);
    if (fr) {
      unit = "fr";
      value = Number(fr[1]);
    } else {
      const pct = WIDTH_PCT_RE.exec(text);
      if (!pct) return null;
      unit = "pct";
      value = Number(pct[1]);
    }
  } else {
    return null;
  }
  if (!Number.isFinite(value) || value <= 0 || value > 100) return null;
  return { unit, value };
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

/** Percent per column (null = auto). fr weights share 100 − Σ fixed %. */
export function resolveColumnWidths(
  columns: ReadonlyArray<Partial<ReportTableColumn>>,
): Array<number | null> {
  const parsed = columns.map((c) => parseColumnWidth(c?.width));
  let pctTotal = 0;
  let frTotal = 0;
  for (const p of parsed) {
    if (!p) continue;
    if (p.unit === "pct") pctTotal += p.value;
    else frTotal += p.value;
  }
  const remaining = Math.max(0, 100 - pctTotal);
  return parsed.map((p) => {
    if (!p) return null;
    if (p.unit === "pct") return round2(p.value);
    if (remaining > 0 && frTotal > 0) return round2((remaining * p.value) / frTotal);
    return null;
  });
}

export function formatWidthPct(value: number): string {
  return `${round2(value)}%`;
}

/** Sum of explicit percent widths (fr / auto excluded). */
export function fixedWidthTotal(columns: ReadonlyArray<Partial<ReportTableColumn>>): number {
  let total = 0;
  for (const c of columns) {
    const p = parseColumnWidth(c.width);
    if (p?.unit === "pct") total += p.value;
  }
  return round2(total);
}

export function columnWidthMode(column: Partial<ReportTableColumn>): TableWidthMode {
  const p = parseColumnWidth(column.width);
  if (!p) return "auto";
  return p.unit;
}

export function columnSums(column: Partial<ReportTableColumn>): boolean {
  return column.sum === true;
}

/** True when the compiler will emit a totals footer for this block. */
export function tableEmitsTotals(block: TableBlockLike): boolean {
  return block.totals_row === true && (block.columns || []).some(columnSums);
}

/** Sanitize one persisted / pasted column (drops unknown keys and bad values). */
export function normalizeTableColumn(raw: unknown): ReportTableColumn | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  const field = typeof r.field === "string" ? r.field.trim() : "";
  if (!field) return null;
  const col: ReportTableColumn = {
    field,
    label: typeof r.label === "string" ? r.label : field,
  };
  if (typeof r.ttype === "string" && r.ttype.trim()) col.ttype = r.ttype.trim();
  if (isTableAlign(r.align)) col.align = r.align;
  const width = parseColumnWidth(r.width);
  if (width) col.width = width.unit === "fr" ? `${width.value}fr` : width.value;
  if (r.sum === true) col.sum = true;
  return col;
}

/** Normalize an `o2m_table` block's columns + totals keys (other blocks untouched). */
export function normalizeTableBlockColumns<T extends TableBlockLike>(block: T): T {
  if (block.type !== "o2m_table") return block;
  const cols = Array.isArray(block.columns)
    ? block.columns
        .map((c) => normalizeTableColumn(c))
        .filter((c): c is ReportTableColumn => c !== null)
    : [];
  const next: T = { ...block, columns: cols.length ? cols : [{ ...DEFAULT_TABLE_COLUMN }] };
  if (block.totals_row !== undefined) next.totals_row = block.totals_row === true;
  if (typeof block.totals_label !== "string") delete next.totals_label;
  return next;
}

/** New column for a schema row: label, ttype hint and type-default align. */
export function columnFromField(
  row: FieldRow | undefined,
  fallbackField = "display_name",
): ReportTableColumn {
  if (!row) {
    return {
      field: fallbackField,
      label: fallbackField === "display_name" ? "Line" : fallbackField,
    };
  }
  const col: ReportTableColumn = {
    field: row.name,
    label: row.field_description || row.name,
    ttype: row.ttype,
  };
  if (isNumericFieldType(row.ttype)) col.align = "right";
  return col;
}

/**
 * Re-point a column at another grounded field. Width survives; align resets to
 * the new type default unless the user picked a non-default; `sum` is dropped
 * if the new field is not numeric.
 */
export function changeColumnField(
  column: ReportTableColumn,
  row: FieldRow | undefined,
  value: string,
): ReportTableColumn {
  const base = columnFromField(row, value);
  const prevDefault = columnDefaultAlign(column.ttype);
  const userAlign = column.align && column.align !== prevDefault ? column.align : undefined;
  const next: ReportTableColumn = { ...base };
  if (userAlign) next.align = userAlign;
  if (column.width !== undefined) next.width = column.width;
  if (column.sum && isNumericFieldType(base.ttype)) next.sum = true;
  return next;
}

/** First related field not already used as a column (falls back to the first). */
export function nextUnusedField(
  columns: ReadonlyArray<ReportTableColumn>,
  fields: ReadonlyArray<FieldRow>,
): FieldRow | undefined {
  const used = new Set(columns.map((c) => c.field));
  return fields.find((f) => !used.has(f.name)) ?? fields[0];
}

/**
 * Client mirror of the API totals gate: summed columns must be numeric on the
 * related model. Returns a human error or null. Unknown related schema → skip
 * (field grounding reports that separately; the API gate stays authoritative).
 */
export function validateTableTotals(
  blocks: ReadonlyArray<TableBlockLike>,
  relatedTypes: Map<string, Map<string, string>>,
): string | null {
  for (const block of blocks) {
    if (block.type !== "o2m_table") continue;
    const o2m = (block.o2m_field || block.field || "").trim().replace(/^doc\./, "");
    const types = relatedTypes.get(o2m);
    if (!types) continue;
    for (const col of block.columns || []) {
      if (!columnSums(col)) continue;
      const ttype = types.get(col.field);
      if (!isNumericFieldType(ttype)) {
        return `totals row can only sum numeric fields; ${o2m}.${col.field} is ${ttype || "unknown"}`;
      }
    }
  }
  return null;
}

/** Inline style for canvas th/td — mirrors the compiler's emitted style. */
export function columnCellStyle(
  align: TableAlign,
  widthPct: number | null,
  withWidth = true,
): { textAlign: TableAlign; width?: string } {
  const style: { textAlign: TableAlign; width?: string } = { textAlign: align };
  if (withWidth && widthPct !== null) style.width = formatWidthPct(widthPct);
  return style;
}
