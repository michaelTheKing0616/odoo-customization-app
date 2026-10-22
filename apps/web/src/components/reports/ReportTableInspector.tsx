"use client";

import { useEffect, useMemo, useState } from "react";
import type { FieldRow } from "@/lib/api";
import {
  ReorderableBlocks,
  moveIndex,
} from "@/components/ui/canvas/ReorderableBlocks";
import { cn } from "@/lib/cn";
import { ScrubNumber } from "@/components/ui/craft";
import type { ReportBlock } from "./ReportCanvas";
import { ReportFieldPicker } from "./ReportFieldPicker";
import {
  DEFAULT_TABLE_COLUMN,
  DEFAULT_TOTALS_LABEL,
  type ReportTableColumn,
  type TableAlign,
  type TableWidthMode,
  changeColumnField,
  columnFromField,
  columnSums,
  columnWidthMode,
  fixedWidthTotal,
  formatWidthPct,
  isNumericFieldType,
  nextUnusedField,
  parseColumnWidth,
  resolveColumnAlign,
  resolveColumnWidths,
} from "./reportTableColumns";
import styles from "./ReportTableInspector.module.css";

type ReportTableInspectorProps = {
  block: ReportBlock;
  /** o2m / m2m fields on the bound model (fields_get). */
  o2mOptions: FieldRow[];
  /** Related comodel fields for the selected lines field (fields_get). */
  relatedFields: FieldRow[];
  activeIndex: number;
  onActiveIndexChange: (index: number) => void;
  onChange: (patch: Partial<ReportBlock>) => void;
  disabled?: boolean;
};

const ALIGN_OPTIONS: Array<{ value: TableAlign; label: string }> = [
  { value: "left", label: "Left" },
  { value: "center", label: "Center" },
  { value: "right", label: "Right" },
];

const WIDTH_MODES: Array<{ value: TableWidthMode; label: string; hint: string }> = [
  { value: "auto", label: "Auto", hint: "Let the PDF engine size this column" },
  { value: "pct", label: "%", hint: "Fixed share of the table width" },
  { value: "fr", label: "Flex", hint: "Share what fixed columns leave" },
];

function AlignGlyph({ align }: { align: TableAlign }) {
  // Three hairline bars, aligned like the text they describe.
  const rows: Array<[number, number]> =
    align === "left"
      ? [[2, 12], [2, 8], [2, 10]]
      : align === "center"
        ? [[2, 12], [4, 8], [3, 10]]
        : [[2, 12], [6, 8], [4, 10]];
  return (
    <svg viewBox="0 0 16 12" width="14" height="11" aria-hidden="true" className={styles.glyph}>
      {rows.map(([x, w], i) => (
        <rect key={i} x={x} y={1 + i * 4} width={w} height="1.5" rx="0.75" />
      ))}
    </svg>
  );
}

function GripGlyph() {
  return (
    <svg viewBox="0 0 8 12" width="8" height="12" aria-hidden="true" className={styles.glyph}>
      {[0, 1, 2].map((r) =>
        [0, 1].map((c) => <circle key={`${r}-${c}`} cx={2 + c * 4} cy={2 + r * 4} r="1" />),
      )}
    </svg>
  );
}

function WidthControl({
  column,
  resolvedPct,
  onChange,
  disabled,
}: {
  column: ReportTableColumn;
  resolvedPct: number | null;
  onChange: (width: number | string | undefined) => void;
  disabled?: boolean;
}) {
  const mode = columnWidthMode(column);
  const parsed = parseColumnWidth(column.width);
  const [draft, setDraft] = useState(parsed ? String(parsed.value) : "");

  useEffect(() => {
    setDraft(parsed ? String(parsed.value) : "");
    // Re-sync when the stored width changes from outside (mode switch / reorder).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [column.width]);

  function setMode(next: TableWidthMode) {
    if (next === mode) return;
    if (next === "auto") onChange(undefined);
    else if (next === "pct") onChange(resolvedPct !== null ? Math.round(resolvedPct) || 20 : 20);
    else onChange("1fr");
  }

  function commit(text: string) {
    setDraft(text);
    const n = Number(text);
    if (!text.trim() || !Number.isFinite(n) || n <= 0 || n > 100) return;
    onChange(mode === "fr" ? `${n}fr` : n);
  }

  return (
    <div className={styles.field}>
      <div className={styles.fieldHead}>
        <span className={styles.fieldLabel}>Width</span>
        <span className={styles.fieldMeta} data-testid="report-table-width-resolved">
          {resolvedPct !== null ? formatWidthPct(resolvedPct) : "auto"}
        </span>
      </div>
      <div className={styles.segmented} role="radiogroup" aria-label="Column width mode">
        {WIDTH_MODES.map((m) => (
          <button
            key={m.value}
            type="button"
            role="radio"
            aria-checked={mode === m.value}
            title={m.hint}
            disabled={disabled}
            data-testid={`report-table-width-mode-${m.value}`}
            className={cn(styles.segment, mode === m.value && styles.segmentOn)}
            onClick={() => setMode(m.value)}
          >
            {m.label}
          </button>
        ))}
      </div>
      {mode !== "auto" ? (
        <label className={styles.inlineInput}>
          <input
            type="number"
            inputMode="decimal"
            min={1}
            max={100}
            step={mode === "fr" ? 1 : 5}
            value={draft}
            disabled={disabled}
            aria-label={mode === "fr" ? "Flex weight" : "Width percent"}
            aria-invalid={draft.trim() !== "" && !parseColumnWidth(draft) ? true : undefined}
            data-testid="report-table-width-input"
            onChange={(e) => commit(e.target.value)}
            className={styles.numberInput}
          />
          {/* Q2 touch 44: drag the unit (or use arrows) to scrub the width. */}
          <ScrubNumber
            value={Number(draft) || 1}
            onChange={(n) => !disabled && commit(String(n))}
            step={mode === "fr" ? 1 : 5}
            min={1}
            max={100}
            label={mode === "fr" ? "Drag to change the flex weight" : "Drag to change the width"}
          >
            <span className={styles.suffix} data-testid="report-table-width-scrub">{mode === "fr" ? "fr" : "%"}</span>
          </ScrubNumber>
        </label>
      ) : null}
    </div>
  );
}

/**
 * PDF-07 — grounded Table Inspector for `o2m_table` blocks.
 * Columns come only from the related model's fields_get. Align / width / totals
 * are presentation hints compiled to allowlisted classes and numeric styles.
 */
export function ReportTableInspector({
  block,
  o2mOptions,
  relatedFields,
  activeIndex,
  onActiveIndexChange,
  onChange,
  disabled = false,
}: ReportTableInspectorProps) {
  const columns: ReportTableColumn[] = block.columns?.length
    ? block.columns
    : [{ ...DEFAULT_TABLE_COLUMN }];
  const active = Math.min(Math.max(0, activeIndex), columns.length - 1);
  const activeCol = columns[active];

  const relatedByName = useMemo(() => {
    const map = new Map<string, FieldRow>();
    for (const f of relatedFields) map.set(f.name, f);
    return map;
  }, [relatedFields]);
  const schemaLoaded = relatedFields.length > 0;

  const typeOf = (c: ReportTableColumn) => relatedByName.get(c.field)?.ttype ?? c.ttype;
  const isNumeric = (c: ReportTableColumn) => isNumericFieldType(typeOf(c));
  const isOrphan = (c: ReportTableColumn) => schemaLoaded && !relatedByName.has(c.field);

  // Resolve with schema types so defaults (numeric → right) match the compiler.
  const typedColumns = columns.map((c) => ({ ...c, ttype: typeOf(c) }));
  const widths = resolveColumnWidths(typedColumns);
  const aligns = typedColumns.map((c) => resolveColumnAlign(c));
  const fixedTotal = fixedWidthTotal(columns);
  // Budget bar: auto columns split whatever resolved widths leave (min 1 unit).
  const resolvedTotal = widths.reduce<number>((sum, w) => sum + (w ?? 0), 0);
  const autoCount = widths.filter((w) => w === null).length;
  const autoShare = autoCount ? Math.max(1, (100 - resolvedTotal) / autoCount) : 1;
  const overBudget = fixedTotal > 100;
  const totalsOn = block.totals_row === true;
  const sumCount = columns.filter(columnSums).length;
  const o2mName = (block.o2m_field || block.field || "").trim();
  const o2mRow = o2mOptions.find((f) => f.name === o2mName);

  function setColumns(next: ReportTableColumn[], nextActive?: number) {
    const safe = next.length ? next : [{ ...DEFAULT_TABLE_COLUMN }];
    onChange({ columns: safe });
    if (nextActive !== undefined) {
      onActiveIndexChange(Math.min(Math.max(0, nextActive), safe.length - 1));
    }
  }

  function patchColumn(index: number, patch: Partial<ReportTableColumn>) {
    const next = columns.map((c, i) => {
      if (i !== index) return c;
      const merged: ReportTableColumn = { ...c, ...patch };
      for (const key of Object.keys(patch) as Array<keyof ReportTableColumn>) {
        if (patch[key] === undefined) delete merged[key];
      }
      return merged;
    });
    setColumns(next);
  }

  function reorder(from: number, to: number) {
    const next = moveIndex(columns, from, to);
    let nextActive = active;
    if (active === from) nextActive = to;
    else if (from < active && to >= active) nextActive = active - 1;
    else if (from > active && to <= active) nextActive = active + 1;
    setColumns(next, nextActive);
  }

  function removeColumn(index: number) {
    const next = columns.filter((_, i) => i !== index);
    setColumns(next, index < active ? active - 1 : index === active ? Math.max(0, active - 1) : active);
  }

  function addColumn() {
    const row = nextUnusedField(columns, relatedFields);
    const col = columnFromField(row);
    setColumns([...columns, col], columns.length);
  }

  const items = columns.map((col, index) => ({ id: `col-${index}`, col, index }));

  return (
    <section className={styles.inspector} data-testid="report-table-inspector" aria-label="Table inspector">
      <header className={styles.head}>
        <p className={styles.eyebrow}>Table</p>
        <p className={styles.title}>
          {o2mRow?.field_description || o2mName || "Pick a lines field"}
          {o2mRow?.relation ? (
            <span className={styles.titleMeta}>{o2mRow.relation}</span>
          ) : null}
        </p>
      </header>

      <ReportFieldPicker
        label="Lines field (o2m / m2m)"
        testId="report-o2m-field-picker"
        value={block.o2m_field || ""}
        fields={o2mOptions}
        allowEmpty
        disabled={disabled}
        emptyLabel="— pick o2m/m2m on model —"
        onChange={(v) =>
          onChange({
            o2m_field: v,
            columns: block.columns?.length ? block.columns : [{ ...DEFAULT_TABLE_COLUMN }],
          })
        }
      />

      <div className={styles.sectionHead}>
        <span>Columns</span>
        <span className={styles.count}>{columns.length}</span>
      </div>

      <div
        className={styles.budget}
        data-testid="report-table-width-budget"
        data-over={overBudget ? "true" : undefined}
        aria-hidden="true"
      >
        {columns.map((c, i) => (
          <span
            key={`${c.field}-${i}`}
            className={cn(styles.budgetSeg, i === active && styles.budgetSegOn)}
            style={{ flexGrow: widths[i] ?? autoShare }}
          />
        ))}
      </div>

      <ReorderableBlocks
        items={items}
        getId={(item) => item.id}
        disabled={disabled || columns.length < 2}
        onReorder={reorder}
        onMove={(id, dir) => {
          const from = Number(id.replace("col-", ""));
          const to = from + dir;
          if (to < 0 || to >= columns.length) return;
          reorder(from, to);
        }}
        className={styles.columnList}
        listProps={{
          "data-testid": "report-o2m-columns",
          "aria-label": "Columns — drag or use arrow keys to reorder",
        }}
        itemProps={(item) => ({
          role: "button",
          tabIndex: 0,
          "data-testid": `report-table-column-row-${item.index}`,
          "aria-pressed": item.index === active,
          className: cn(styles.columnRow, item.index === active && styles.columnRowOn),
          onClick: () => onActiveIndexChange(item.index),
          onKeyDown: (e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              onActiveIndexChange(item.index);
            }
          },
        })}
      >
        {(item) => {
          const c = item.col;
          const i = item.index;
          return (
            <>
              <span className={styles.grip} title="Drag to reorder">
                <GripGlyph />
              </span>
              <span className={styles.colText}>
                <span className={styles.colLabel}>{c.label || c.field}</span>
                <span className={styles.colField}>
                  {c.field}
                  {isOrphan(c) ? (
                    <span className={styles.orphan} data-testid={`report-table-column-orphan-${i}`}>
                      not on model
                    </span>
                  ) : null}
                </span>
              </span>
              <span className={styles.badges}>
                <span className={styles.badge} title={`Align ${aligns[i]}`} data-testid={`report-table-column-align-badge-${i}`}>
                  <AlignGlyph align={aligns[i]} />
                </span>
                {widths[i] !== null ? (
                  <span className={styles.badge}>{formatWidthPct(widths[i] as number)}</span>
                ) : null}
                {totalsOn && columnSums(c) ? (
                  <span className={cn(styles.badge, styles.badgeSum)} title="Summed in totals row">
                    Σ
                  </span>
                ) : null}
              </span>
              <button
                type="button"
                className={styles.remove}
                aria-label={`Remove column ${c.label || c.field}`}
                data-testid={`report-table-column-remove-${i}`}
                disabled={disabled}
                onKeyDown={(e) => {
                  if (e.key === "ArrowUp" || e.key === "ArrowDown") e.stopPropagation();
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  removeColumn(i);
                }}
              >
                ×
              </button>
            </>
          );
        }}
      </ReorderableBlocks>

      <button
        type="button"
        className={styles.addColumn}
        data-testid="report-o2m-add-column"
        disabled={disabled}
        onClick={addColumn}
      >
        + Add column
      </button>

      {overBudget ? (
        <p className={styles.warn} role="status" data-testid="report-table-width-warning">
          Fixed widths add up to {formatWidthPct(fixedTotal)} — the PDF engine will squeeze
          columns. Bring them under 100%.
        </p>
      ) : null}

      {activeCol ? (
        <div className={styles.editor} data-testid="report-table-column-editor">
          <p className={styles.editorTitle}>
            Column {active + 1}
            <span className={styles.titleMeta}>{typeOf(activeCol) || "type unknown"}</span>
          </p>
          <ReportFieldPicker
            label="Field"
            testId={`report-o2m-column-field-${active}`}
            value={activeCol.field}
            fields={relatedFields}
            disabled={disabled}
            onChange={(v) => {
              const row = relatedByName.get(v);
              const next = columns.slice();
              next[active] = changeColumnField(activeCol, row, v);
              setColumns(next);
            }}
          />
          <label className={styles.field}>
            <span className={styles.fieldLabel}>Header</span>
            <input
              value={activeCol.label}
              disabled={disabled}
              data-testid={`report-o2m-column-label-${active}`}
              onChange={(e) => patchColumn(active, { label: e.target.value })}
              className={styles.textInput}
            />
          </label>

          <div className={styles.field}>
            <span className={styles.fieldLabel}>Align</span>
            <div className={styles.segmented} role="radiogroup" aria-label="Column alignment">
              {ALIGN_OPTIONS.map((opt) => {
                const on = aligns[active] === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    role="radio"
                    aria-checked={on}
                    aria-label={`Align ${opt.label.toLowerCase()}`}
                    title={opt.label}
                    disabled={disabled}
                    data-testid={`report-table-align-${opt.value}`}
                    className={cn(styles.segment, on && styles.segmentOn)}
                    onClick={() => patchColumn(active, { align: opt.value })}
                  >
                    <AlignGlyph align={opt.value} />
                  </button>
                );
              })}
            </div>
          </div>

          <WidthControl
            key={`${active}-${activeCol.field}`}
            column={activeCol}
            resolvedPct={widths[active]}
            disabled={disabled}
            onChange={(width) => patchColumn(active, { width })}
          />

          {totalsOn ? (
            <div className={styles.switchRow}>
              <span>
                <span className={styles.fieldLabel}>Sum in totals</span>
                {!isNumeric(activeCol) ? (
                  <span className={styles.hint} data-testid="report-table-col-sum-hint">
                    Only number fields (integer, float, monetary) can be summed.
                  </span>
                ) : null}
              </span>
              <button
                type="button"
                role="switch"
                aria-checked={columnSums(activeCol)}
                aria-label="Sum this column in the totals row"
                disabled={disabled || !isNumeric(activeCol)}
                data-testid="report-table-col-sum"
                className={cn(styles.switch, columnSums(activeCol) && styles.switchOn)}
                onClick={() =>
                  patchColumn(active, { sum: columnSums(activeCol) ? undefined : true })
                }
              >
                <span className={styles.knob} />
              </button>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className={styles.totals}>
        <div className={styles.switchRow}>
          <span>
            <span className={styles.fieldLabel}>Totals row</span>
            <span className={styles.hint}>Pure QWeb sum — works on Odoo Online.</span>
          </span>
          <button
            type="button"
            role="switch"
            aria-checked={totalsOn}
            aria-label="Totals row"
            disabled={disabled}
            data-testid="report-table-totals-toggle"
            className={cn(styles.switch, totalsOn && styles.switchOn)}
            onClick={() => {
              if (totalsOn) {
                onChange({ totals_row: false });
                return;
              }
              // First enable: pre-mark numeric columns so the footer is useful at once.
              const anySum = columns.some(columnSums);
              const next = anySum
                ? columns
                : columns.map((c) => (isNumeric(c) ? { ...c, sum: true } : c));
              onChange({ totals_row: true, columns: next });
            }}
          >
            <span className={styles.knob} />
          </button>
        </div>
        {totalsOn ? (
          <>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>Caption</span>
              <input
                value={block.totals_label ?? ""}
                placeholder={DEFAULT_TOTALS_LABEL}
                disabled={disabled}
                data-testid="report-table-totals-label"
                onChange={(e) => onChange({ totals_label: e.target.value })}
                className={styles.textInput}
              />
            </label>
            {sumCount === 0 ? (
              <p className={styles.hint} data-testid="report-table-totals-empty">
                No number columns are summed yet — select a number column and switch on
                “Sum in totals”.
              </p>
            ) : (
              <p className={styles.hint}>
                Summing {sumCount} column{sumCount === 1 ? "" : "s"}.
              </p>
            )}
          </>
        ) : null}
      </div>
    </section>
  );
}
