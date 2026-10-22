"use client";

import type { PreviewField } from "@/lib/draft-form-preview";
import { CalendarIcon, CaretIcon, ExternalIcon } from "./OdooIcons";

type OdooFieldProps = {
  field: PreviewField;
  highlighted?: boolean;
  onClick?: () => void;
  /** Wide = label above, value spans the full group (one2many lists, html). */
  layout?: "row" | "wide";
};

type RelationColumn = { name: string; string: string; ttype?: string };

const TYPE_HINTS: Record<string, string> = {
  char: "Text",
  text: "Long text",
  html: "Rich text",
  integer: "Whole number",
  float: "Decimal",
  monetary: "Amount",
  boolean: "Checkbox",
  selection: "Choice",
  date: "Date",
  datetime: "Date and time",
  many2one: "Link to one record",
  many2many: "Tags",
  one2many: "Lines",
  binary: "File",
  image: "Image",
};

function isStockPlaceholder(field: PreviewField): boolean {
  return field.name.startsWith("_host_");
}

export function fieldKind(field: PreviewField): string {
  const ttype = (field.ttype || "char").toLowerCase();
  const widget = (field.widget || "").toLowerCase();
  if (widget === "many2many_tags") return "many2many";
  if (widget === "html") return "html";
  if (widget === "boolean_toggle" || widget === "boolean") return "boolean";
  if (widget === "radio") return "selection";
  return ttype;
}

/** One2many / embedded many2many render as a list, not an inline value. */
export function isWideField(field: PreviewField): boolean {
  const kind = fieldKind(field);
  if (kind === "one2many") return true;
  if (kind === "html") return true;
  return kind === "many2many" && Boolean(field.relationColumns?.length) && field.widget !== "many2many_tags";
}

export function fieldTypeHint(field: PreviewField): string {
  const kind = fieldKind(field);
  return TYPE_HINTS[kind] || kind;
}

function charSample(field: PreviewField): string {
  // Honest sample: never reuse the field label as the value.
  const sample = isStockPlaceholder(field)
    ? field.name === "_host_name"
      ? "Sample contact"
      : ""
    : field.name === "x_name" || field.name.endsWith("_name")
      ? "Sample record"
      : "Sample";
  const label = (field.string || field.name || "").trim().toLowerCase();
  if (["false", "true", "checkbox", "boolean"].includes(sample.toLowerCase())) return "";
  if (sample.trim() && sample.trim().toLowerCase() === label) return "Sample";
  return sample;
}

function sampleCell(col: RelationColumn): string {
  const ct = (col.ttype || "char").toLowerCase();
  const n = `${col.name} ${col.string}`.toLowerCase();
  if (ct === "boolean" || /\bdone\b/.test(n)) return "";
  if (ct === "many2one" || /product/.test(n)) return "Product";
  if (ct === "float" || ct === "integer" || ct === "monetary" || /\bqty\b|quantity/.test(n)) return "1.00";
  if (ct === "date" || ct === "datetime") return "09/01/2026";
  if (/checklist|item|label|line/.test(n)) return "Sample item";
  return "Sample";
}

function ListWidget({ field }: { field: PreviewField }) {
  const cols: RelationColumn[] =
    field.relationColumns && field.relationColumns.length > 0
      ? field.relationColumns
      : [
          { name: "x_name", string: "Line", ttype: "char" },
          { name: "x_done", string: "Done", ttype: "boolean" },
        ];
  return (
    <span
      className="ofp-o2m"
      data-testid={`odoo-widget-o2m-${field.name}`}
      data-relation={field.relation || ""}
    >
      <span className="ofp-o2m-scroll">
        <table className="ofp-o2m-table">
          <thead>
            <tr>
              {cols.map((col) => (
                <th key={col.name} data-ttype={col.ttype || "char"}>
                  {col.string || col.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[0, 1].map((row) => (
              <tr key={row} className={row === 1 ? "is-faded" : undefined}>
                {cols.map((col) => {
                  const ct = (col.ttype || "char").toLowerCase();
                  const isBool = ct === "boolean" || /\bdone\b/i.test(`${col.name} ${col.string}`);
                  return (
                    <td key={col.name} data-ttype={col.ttype || "char"}>
                      {isBool ? <span className="ofp-checkbox" aria-hidden /> : sampleCell(col)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </span>
      <span className="ofp-o2m-add">Add a line</span>
    </span>
  );
}

function WidgetBody({ field }: { field: PreviewField }) {
  const kind = fieldKind(field);
  const widget = (field.widget || "").toLowerCase();

  if (kind === "boolean") {
    if (widget === "boolean_toggle") {
      return (
        <span className="ofp-bool" data-testid={`odoo-widget-boolean-${field.name}`} data-widget="boolean_toggle">
          <span className="ofp-toggle" aria-hidden />
        </span>
      );
    }
    return (
      <span className="ofp-bool" data-testid={`odoo-widget-boolean-${field.name}`} data-widget="checkbox">
        <span className="ofp-checkbox" aria-hidden data-checked="false" />
      </span>
    );
  }
  if (kind === "selection") {
    const selected = (field.selection || [])[0];
    return (
      <span className="ofp-input ofp-input--select" data-testid={`odoo-widget-selection-${field.name}`}>
        <span className="ofp-input-text">{selected?.label || selected?.value || ""}</span>
        <CaretIcon className="ofp-icon ofp-caret" />
      </span>
    );
  }
  if (kind === "many2one") {
    const stock = isStockPlaceholder(field);
    return (
      <span className="ofp-input ofp-input--m2o" data-testid={`odoo-widget-m2o-${field.name}`}>
        <span className="ofp-input-text ofp-m2o-value">{stock ? "" : "Related record"}</span>
        <CaretIcon className="ofp-icon ofp-caret" />
        {stock ? null : <ExternalIcon className="ofp-icon ofp-m2o-open" />}
      </span>
    );
  }
  if (kind === "many2many" && !isWideField(field)) {
    return (
      <span className="ofp-input ofp-input--tags" data-testid={`odoo-widget-tags-${field.name}`}>
        <span className="ofp-tag" data-tone="1">Tag A</span>
        <span className="ofp-tag" data-tone="2">Tag B</span>
        <CaretIcon className="ofp-icon ofp-caret" />
      </span>
    );
  }
  if (kind === "one2many" || kind === "many2many") {
    return <ListWidget field={field} />;
  }
  if (kind === "date" || kind === "datetime") {
    return (
      <span
        className="ofp-input ofp-input--date"
        data-testid={`odoo-widget-${kind}-${field.name}`}
      >
        <span className="ofp-input-text">{kind === "date" ? "09/01/2026" : "09/01/2026 09:00"}</span>
        <CalendarIcon className="ofp-icon ofp-date-icon" />
      </span>
    );
  }
  if (kind === "monetary") {
    return (
      <span className="ofp-input ofp-input--num" data-testid={`odoo-widget-monetary-${field.name}`}>
        <span className="ofp-input-text">
          <span className="ofp-currency">$</span>
          <span className="ofp-amount">0.00</span>
        </span>
      </span>
    );
  }
  if (kind === "float" || kind === "integer") {
    return (
      <span className="ofp-input ofp-input--num" data-testid={`odoo-widget-number-${field.name}`}>
        <span className="ofp-input-text">{kind === "integer" ? "0" : "0.00"}</span>
      </span>
    );
  }
  if (kind === "html") {
    return (
      <span className="ofp-html" data-testid={`odoo-widget-html-${field.name}`}>
        <span className="ofp-html-toolbar" aria-hidden>
          <b>B</b>
          <i>I</i>
          <u>U</u>
          <span className="ofp-html-sep" />
          <span>List</span>
          <span>Link</span>
        </span>
        <span className="ofp-html-body">Type &quot;/&quot; for commands</span>
      </span>
    );
  }
  if (kind === "text") {
    return (
      <span className="ofp-input ofp-input--text" data-testid={`odoo-widget-text-${field.name}`}>
        <span className="ofp-input-text">{isStockPlaceholder(field) ? "" : "Multiline notes"}</span>
      </span>
    );
  }
  return (
    <span className="ofp-input" data-testid={`odoo-widget-char-${field.name}`}>
      {charSample(field)}
    </span>
  );
}

export function OdooField({ field, highlighted, onClick, layout }: OdooFieldProps) {
  const stock = isStockPlaceholder(field);
  const wide = layout === "wide" || (layout === undefined && isWideField(field));
  const deferred = field.deferred || null;
  const label = field.string || field.name;
  const hint = fieldTypeHint(field);
  const rowClass = [
    "ofp-field",
    wide ? "ofp-field--wide" : "",
    stock ? "is-stock" : "",
    highlighted ? "is-extension" : "",
    field.required ? "is-required" : "",
    deferred ? "is-deferred" : "",
  ]
    .filter(Boolean)
    .join(" ");
  const body = (
    <>
      <div className="ofp-label">
        <span className="ofp-label-text">{label}</span>
        {field.required ? (
          <span className="ofp-required" aria-hidden>
            *
          </span>
        ) : null}
        <span className="ofp-type-hint" aria-hidden>
          {hint}
        </span>
      </div>
      <div
        className={`ofp-value ${highlighted ? "field-highlight" : ""} ${stock ? "is-stock" : ""}`}
        data-testid={`odoo-field-${field.name}`}
        data-ttype={field.ttype || "char"}
        title={`${label}: ${hint}`}
      >
        <WidgetBody field={field} />
        {deferred ? (
          <span className="ofp-deferred-badge" data-testid={`odoo-field-deferred-${field.name}`} data-status={deferred}>
            {deferred === "left_out" ? "Left out" : "Install later"}
          </span>
        ) : null}
      </div>
    </>
  );
  if (onClick) {
    return (
      <button type="button" className={`${rowClass} w-full text-left`} onClick={onClick} aria-label={`${label} ${field.name}`}>
        {body}
      </button>
    );
  }
  return (
    <div className={rowClass} data-kind={fieldKind(field)}>
      {body}
    </div>
  );
}
