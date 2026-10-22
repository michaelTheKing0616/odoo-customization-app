"use client";

import type { CSSProperties } from "react";
import {
  ReorderableBlocks,
  moveIndex,
} from "@/components/ui/canvas/ReorderableBlocks";
import { cn } from "@/lib/cn";
import styles from "./ReportCanvas.module.css";
import {
  DEFAULT_TOTALS_LABEL,
  type ReportTableColumn,
  columnCellStyle,
  columnSums,
  formatWidthPct,
  isNumericFieldType,
  resolveColumnAlign,
  resolveColumnWidths,
  tableEmitsTotals,
} from "./reportTableColumns";

export type ReportBlockType =
  | "heading"
  | "field"
  | "label_field"
  | "o2m_table"
  | "image"
  | "divider"
  | "text"
  | "page_break";

export type ReportBlock = {
  id: string;
  type: ReportBlockType;
  text?: string;
  field?: string;
  label?: string;
  o2m_field?: string;
  level?: number;
  image_src?: string;
  /** PDF-07 Table Inspector: field/label + optional align, width, sum, ttype. */
  columns?: ReportTableColumn[];
  /** Emit a QWeb totals footer for columns with `sum: true`. */
  totals_row?: boolean;
  /** Totals row caption (escaped; PDF-05 refuses QWeb-looking text). */
  totals_label?: string;
};

export type ReportDesignSpec = {
  name: string;
  model: string;
  report_key: string;
  use_external_layout: boolean;
  t_lang?: string | null;
  mode: "primary" | "inherit";
  inherit?: {
    base_report_key: string;
    /** PDF-03 slot; compiler maps to one xpath + position. */
    slot?: "header" | "before_body" | "after_body" | "footer";
    xpath: string;
    position: "inside" | "after" | "before" | "replace";
  };
  blocks: ReportBlock[];
};

/** Millimetre geometry for the on-canvas sheet (Odoo report.paperformat units). */
export type PaperFormatSpec = {
  label: string;
  widthMm: number;
  heightMm: number;
  marginTopMm: number;
  marginBottomMm: number;
  marginLeftMm: number;
  marginRightMm: number;
};

/** Odoo European A4 defaults (mm). */
export const A4_PAPER: PaperFormatSpec = {
  label: "A4",
  widthMm: 210,
  heightMm: 297,
  marginTopMm: 40,
  marginBottomMm: 32,
  marginLeftMm: 7,
  marginRightMm: 7,
};

export const US_LETTER_PAPER: PaperFormatSpec = {
  label: "US Letter",
  widthMm: 215.9,
  heightMm: 279.4,
  marginTopMm: 40,
  marginBottomMm: 32,
  marginLeftMm: 7,
  marginRightMm: 7,
};

const PAPER_PRESETS: Record<string, PaperFormatSpec> = {
  a4: A4_PAPER,
  "european a4": A4_PAPER,
  letter: US_LETTER_PAPER,
  "us letter": US_LETTER_PAPER,
  "us_letter": US_LETTER_PAPER,
};

export const EMPTY_CANVAS_SENTENCE = "This page has no blocks yet.";
export const EMPTY_CANVAS_ACTION = "Add a block";

/** Cream paper surface — stays paper-colored in light and dark UI themes. */
export const REPORT_PAPER_COLOR = "#f7f3eb";
export const REPORT_INK_COLOR = "#1c1917";

/** MIME for palette → report canvas HTML5 drops (PDF-02). */
export const ODOO_REPORT_BLOCK_MIME = "text/odoo-report-block";

export function setReportPaletteDragData(dt: DataTransfer, blockType: string): void {
  dt.setData(ODOO_REPORT_BLOCK_MIME, blockType);
  dt.setData("text/plain", blockType);
  dt.effectAllowed = "copy";
}

export function readReportPaletteBlockType(
  dt: DataTransfer | null | undefined,
): ReportBlockType | null {
  if (!dt) return null;
  const raw = (dt.getData(ODOO_REPORT_BLOCK_MIME) || dt.getData("text/plain") || "").trim();
  if (!raw) return null;
  const allowed: ReportBlockType[] = [
    "heading",
    "field",
    "label_field",
    "o2m_table",
    "image",
    "divider",
    "text",
    "page_break",
  ];
  return (allowed as string[]).includes(raw) ? (raw as ReportBlockType) : null;
}

export function isReportPaletteDrag(dt: DataTransfer | null | undefined): boolean {
  if (!dt) return false;
  if (Array.from(dt.types || []).includes(ODOO_REPORT_BLOCK_MIME)) return true;
  // Synthetic / jsdom events may omit types while still exposing getData on drop.
  try {
    return Boolean(dt.getData(ODOO_REPORT_BLOCK_MIME));
  } catch {
    return false;
  }
}

export { moveIndex as reorderReportBlocks };

const AMOUNT_FIELD_RE =
  /(amount|price|total|subtotal|tax|balance|debit|credit|rate|qty|quantity|untaxed|residual|unit_price|price_unit)/i;

export function normalizePaperLabel(label?: string | null): string {
  return (label || "A4").trim().toLowerCase();
}

export function resolvePaperFormat(
  label?: string | null,
  overrides?: Partial<Omit<PaperFormatSpec, "label">>,
): PaperFormatSpec {
  const key = normalizePaperLabel(label);
  const base = PAPER_PRESETS[key] ?? {
    ...A4_PAPER,
    label: (label || "A4").trim() || "A4",
  };
  return {
    ...base,
    label: (label || base.label).trim() || base.label,
    ...overrides,
  };
}

/** Width ÷ height. A4 ≈ 0.70707. */
export function paperAspectRatio(paper: PaperFormatSpec): number {
  return paper.widthMm / paper.heightMm;
}

/** Absolute percent error between two ratios. */
export function ratioErrorPercent(actual: number, expected: number): number {
  if (expected === 0) return Infinity;
  return (Math.abs(actual - expected) / expected) * 100;
}

export function ratioWithinTolerance(
  actual: number,
  expected: number,
  tolerancePercent = 2,
): boolean {
  return ratioErrorPercent(actual, expected) <= tolerancePercent;
}

export function isAmountField(name?: string | null): boolean {
  if (!name) return false;
  return AMOUNT_FIELD_RE.test(name);
}

export function isAmountColumn(column: { field: string; label?: string }): boolean {
  return isAmountField(column.field) || isAmountField(column.label);
}

/**
 * Convert paper mm margins into CSS padding percentages.
 * CSS % padding is resolved against the containing block WIDTH on all sides,
 * so each margin is expressed as (mm / paper.widthMm) * 100.
 */
export function paperPaddingStyle(paper: PaperFormatSpec): CSSProperties {
  const top = (paper.marginTopMm / paper.widthMm) * 100;
  const bottom = (paper.marginBottomMm / paper.widthMm) * 100;
  const left = (paper.marginLeftMm / paper.widthMm) * 100;
  const right = (paper.marginRightMm / paper.widthMm) * 100;
  return {
    ["--report-pad-top" as string]: `${top}%`,
    ["--report-pad-bottom" as string]: `${bottom}%`,
    ["--report-pad-left" as string]: `${left}%`,
    ["--report-pad-right" as string]: `${right}%`,
  };
}

type ReportCanvasProps = {
  blocks: ReportBlock[];
  paperLabel?: string;
  /** Optional full geometry; overrides the preset resolved from paperLabel. */
  paper?: Partial<PaperFormatSpec>;
  useExternalLayout?: boolean;
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  onMove?: (id: string, dir: -1 | 1) => void;
  /** Pointer drag destination index (0..length-1). */
  onReorder?: (fromIndex: number, toIndex: number) => void;
  /** Insert a palette block type at insertIndex (0..length). */
  onInsertBlock?: (type: ReportBlockType, insertIndex: number) => void;
  /** Empty-state primary action (palette / add). */
  onAddBlock?: () => void;
  documentTitle?: string;
  /** PDF-07: column highlighted by the Table Inspector (selected table only). */
  activeColumn?: { blockId: string; index: number } | null;
  /** PDF-07: clicking a header on the paper focuses that column in the inspector. */
  onSelectColumn?: (blockId: string, index: number) => void;
};

function blockPreview(block: ReportBlock): string {
  switch (block.type) {
    case "heading":
      return block.text || "Heading";
    case "field":
      return `[${block.field || "field"}]`;
    case "label_field":
      return `${block.label || "Label"}: [${block.field || "field"}]`;
    case "o2m_table":
      return `Table: ${block.o2m_field || "line_ids"}`;
    case "image":
      return block.image_src === "company_logo" ? "Company logo" : `Image: ${block.field || "?"}`;
    case "divider":
      return "— — —";
    case "page_break":
      return "Page break";
    default:
      return block.text || "Text";
  }
}

function BlockContent({
  block,
  activeColumnIndex = null,
  onSelectColumn,
}: {
  block: ReportBlock;
  activeColumnIndex?: number | null;
  onSelectColumn?: (index: number) => void;
}) {
  if (block.type === "heading") {
    const isDisplay = !block.level || block.level <= 1;
    return (
      <p className={isDisplay ? styles.titleDisplay : styles.sectionHeading}>
        {blockPreview(block)}
      </p>
    );
  }

  if (block.type === "divider") {
    return <hr className={styles.hairline} />;
  }

  if (block.type === "page_break") {
    return <p className={styles.pageBreak}>{blockPreview(block)}</p>;
  }

  if (block.type === "image") {
    return <div className={styles.logoSlot}>{blockPreview(block)}</div>;
  }

  if (block.type === "o2m_table") {
    const columns: ReportTableColumn[] = block.columns?.length
      ? block.columns
      : [{ field: "name", label: "Line" }];
    // Same resolution as report_design.emit_o2m_table → paper matches the PDF.
    const widths = resolveColumnWidths(columns);
    const aligns = columns.map((c) => resolveColumnAlign(c));
    const showTotals = tableEmitsTotals(block);
    const numeric = (c: ReportTableColumn) =>
      isNumericFieldType(c.ttype) || (!c.ttype && isAmountColumn(c));
    const colProps = (i: number) => ({
      "data-col-index": i,
      "data-align": aligns[i],
      "data-active-col": activeColumnIndex === i ? "true" : undefined,
    });
    return (
      <table
        className={styles.table}
        data-testid={`report-table-${block.id}`}
        data-totals={showTotals ? "true" : undefined}
      >
        <thead>
          <tr>
            {columns.map((c, i) => (
              <th
                key={`${c.field}-${i}`}
                {...colProps(i)}
                data-width={widths[i] !== null ? formatWidthPct(widths[i] as number) : "auto"}
                className={cn(
                  numeric(c) && styles.amountCol,
                  activeColumnIndex === i && styles.activeCol,
                )}
                style={columnCellStyle(aligns[i], widths[i])}
                scope="col"
                onClick={onSelectColumn ? () => onSelectColumn(i) : undefined}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            {columns.map((c, i) => (
              <td
                key={`${c.field}-${i}`}
                {...colProps(i)}
                className={cn(
                  numeric(c) && cn(styles.amountCol, styles.amount),
                  activeColumnIndex === i && styles.activeCol,
                )}
                style={columnCellStyle(aligns[i], widths[i])}
              >
                {i === 0 ? (
                  <span className={styles.muted}>
                    … lines from {block.o2m_field || "line_ids"} …
                  </span>
                ) : numeric(c) ? (
                  <span className={styles.amount} data-tabular-nums="true">
                    {c.ttype === "integer" ? "3" : "1,250.00"}
                  </span>
                ) : (
                  <span className={styles.muted}>—</span>
                )}
              </td>
            ))}
          </tr>
        </tbody>
        {showTotals ? (
          <tfoot data-testid={`report-table-totals-${block.id}`}>
            <tr className={styles.totalsRow}>
              {columns.map((c, i) => (
                <td
                  key={`${c.field}-${i}`}
                  {...colProps(i)}
                  className={cn(
                    columnSums(c) && styles.amount,
                    activeColumnIndex === i && styles.activeCol,
                  )}
                  style={columnCellStyle(aligns[i], null, false)}
                >
                  {columnSums(c) ? (
                    <span className={styles.amount} data-tabular-nums="true" data-sum-cell="true">
                      {c.ttype === "integer" ? "9" : "3,750.00"}
                    </span>
                  ) : i === 0 ? (
                    <span>{(block.totals_label || "").trim() || DEFAULT_TOTALS_LABEL}</span>
                  ) : null}
                </td>
              ))}
            </tr>
          </tfoot>
        ) : null}
      </table>
    );
  }

  if (block.type === "label_field") {
    return (
      <p className={styles.body}>
        <span className={styles.label}>{block.label || "Label"}: </span>
        <span
          className={cn(styles.fieldToken, isAmountField(block.field) && styles.amount)}
          data-tabular-nums={isAmountField(block.field) ? "true" : undefined}
        >
          [{block.field || "field"}]
        </span>
      </p>
    );
  }

  if (block.type === "field") {
    return (
      <p
        className={cn(styles.body, styles.fieldToken, isAmountField(block.field) && styles.amount)}
        data-tabular-nums={isAmountField(block.field) ? "true" : undefined}
      >
        {blockPreview(block)}
      </p>
    );
  }

  return <p className={styles.body}>{blockPreview(block)}</p>;
}

export function ReportCanvas({
  blocks,
  paperLabel = "A4",
  paper: paperOverrides,
  useExternalLayout = true,
  selectedId,
  onSelect,
  onMove,
  onReorder,
  onInsertBlock,
  onAddBlock,
  documentTitle,
  activeColumn = null,
  onSelectColumn,
}: ReportCanvasProps) {
  const paper = resolvePaperFormat(paperLabel, paperOverrides);
  const ratio = paperAspectRatio(paper);
  const padStyle = paperPaddingStyle(paper);

  const paperStyle: CSSProperties = {
    aspectRatio: `${paper.widthMm} / ${paper.heightMm}`,
    backgroundColor: REPORT_PAPER_COLOR,
    color: REPORT_INK_COLOR,
    boxShadow: "none",
    ...padStyle,
  };

  return (
    <div className={styles.stage} data-testid="report-canvas-stage-inner">
      <article
        className={styles.paper}
        data-testid="report-paper"
        data-paper-label={paper.label}
        data-paper-width-mm={paper.widthMm}
        data-paper-height-mm={paper.heightMm}
        data-paper-ratio={ratio.toFixed(6)}
        data-paper-surface={REPORT_PAPER_COLOR}
        style={paperStyle}
        aria-label={`${paper.label} report canvas`}
      >
        {useExternalLayout && (
          <header className={styles.headerBand} data-testid="report-header-band">
            External layout · header · {paper.label}
            {documentTitle ? ` · ${documentTitle}` : null}
          </header>
        )}

        <div className={styles.pageBody} data-testid="report-page-body">
          <ReorderableBlocks
            items={blocks}
            getId={(block) => block.id}
            disabled={!onMove && !onReorder}
            onMove={onMove}
            onReorder={onReorder}
            externalDrop={
              onInsertBlock
                ? {
                    canAccept: (dt) => isReportPaletteDrag(dt),
                    onDrop: (dt, insertIndex) => {
                      const type = readReportPaletteBlockType(dt);
                      if (type) onInsertBlock(type, insertIndex);
                    },
                  }
                : undefined
            }
            className={styles.blocks}
            listProps={{ "data-testid": "report-blocks" }}
            empty={
              <div className={styles.empty} data-testid="report-canvas-empty">
                <p className={styles.emptySentence}>{EMPTY_CANVAS_SENTENCE}</p>
                <button
                  type="button"
                  className={styles.emptyAction}
                  data-testid="report-canvas-add-block"
                  onClick={() => onAddBlock?.()}
                  disabled={!onAddBlock}
                >
                  {EMPTY_CANVAS_ACTION}
                </button>
              </div>
            }
            itemProps={(block) => {
              const selected = selectedId === block.id;
              return {
                role: "button",
                tabIndex: 0,
                "data-testid": `report-block-${block.id}`,
                "aria-pressed": selected,
                className: cn(styles.block, selected && styles.blockSelected),
                onClick: () => onSelect?.(block.id),
                onKeyDown: (e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect?.(block.id);
                  }
                },
              };
            }}
          >
            {(block) => (
              <>
                <BlockContent
                  block={block}
                  activeColumnIndex={
                    activeColumn && activeColumn.blockId === block.id && selectedId === block.id
                      ? activeColumn.index
                      : null
                  }
                  onSelectColumn={
                    onSelectColumn && block.type === "o2m_table"
                      ? (index) => onSelectColumn(block.id, index)
                      : undefined
                  }
                />
                {onMove && (
                  <div className={styles.moveControls}>
                    <button
                      type="button"
                      className={styles.moveBtn}
                      aria-label="Move block up"
                      onPointerDown={(e) => e.stopPropagation()}
                      onClick={(e) => {
                        e.stopPropagation();
                        onMove(block.id, -1);
                      }}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className={styles.moveBtn}
                      aria-label="Move block down"
                      onPointerDown={(e) => e.stopPropagation()}
                      onClick={(e) => {
                        e.stopPropagation();
                        onMove(block.id, 1);
                      }}
                    >
                      ↓
                    </button>
                  </div>
                )}
              </>
            )}
          </ReorderableBlocks>
        </div>

        {useExternalLayout && (
          <footer className={styles.footerBand} data-testid="report-footer-band">
            External layout · footer · {paper.label}
          </footer>
        )}
      </article>
    </div>
  );
}

export const RENTAL_AGREEMENT_STARTER: ReportBlock[] = [
  { id: "h1", type: "heading", text: "Rental Agreement", level: 1 },
  { id: "logo", type: "image", image_src: "company_logo" },
  { id: "cust", type: "label_field", label: "Customer", field: "partner_id" },
  { id: "veh", type: "label_field", label: "Vehicle", field: "vehicle_id" },
  { id: "dates", type: "label_field", label: "Period", field: "date_start" },
  {
    id: "lines",
    type: "o2m_table",
    o2m_field: "line_ids",
    columns: [
      { field: "product_id", label: "Item" },
      { field: "price_unit", label: "Rate" },
    ],
  },
  { id: "sig", type: "text", text: "Signed: _________________________" },
];
