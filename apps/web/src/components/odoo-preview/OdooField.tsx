"use client";

import type { PreviewField } from "@/lib/draft-form-preview";

type OdooFieldProps = {
  field: PreviewField;
  highlighted?: boolean;
  onClick?: () => void;
};

function isStockPlaceholder(field: PreviewField): boolean {
  return field.name.startsWith("_host_");
}

function WidgetBody({ field }: { field: PreviewField }) {
  const ttype = (field.ttype || "char").toLowerCase();
  const widget = (field.widget || "").toLowerCase();

  if (ttype === "boolean" || widget === "boolean" || widget === "boolean_toggle") {
    const useToggle = widget === "boolean_toggle";
    if (useToggle) {
      return (
        <span
          className="odoo-widget-boolean"
          data-testid={`odoo-widget-boolean-${field.name}`}
          data-widget="boolean_toggle"
        >
          <span className="odoo-widget-toggle" aria-hidden />
          <span className="odoo-widget-toggle-label">No</span>
        </span>
      );
    }
    return (
      <span
        className="odoo-widget-boolean"
        data-testid={`odoo-widget-boolean-${field.name}`}
        data-widget="checkbox"
      >
        <span className="odoo-widget-checkbox" aria-hidden data-checked="false" />
      </span>
    );
  }

  if (ttype === "selection" || widget === "selection" || widget === "radio") {
    const options = field.selection || [];
    const selected = options[0];
    return (
      <span className="odoo-widget-selection" data-testid={`odoo-widget-selection-${field.name}`}>
        <span className="odoo-widget-selection-value">
          {selected?.label || selected?.value || "—"}
        </span>
        <span className="odoo-widget-caret" aria-hidden>
          ▾
        </span>
      </span>
    );
  }

  if (ttype === "many2one" || widget === "many2one") {
    return (
      <span className="odoo-widget-m2o" data-testid={`odoo-widget-m2o-${field.name}`}>
        <span className="odoo-widget-m2o-chip">
          {isStockPlaceholder(field) ? "—" : "Related record"}
        </span>
        <span className="odoo-widget-m2o-open" aria-hidden>
          ↗
        </span>
      </span>
    );
  }

  if (ttype === "many2many" || ttype === "one2many" || widget === "many2many_tags") {
    return (
      <span className="odoo-widget-tags" data-testid={`odoo-widget-tags-${field.name}`}>
        <span className="odoo-widget-tag">Tag A</span>
        <span className="odoo-widget-tag">Tag B</span>
      </span>
    );
  }

  if (ttype === "date" || widget === "date") {
    return (
      <span className="odoo-widget-date" data-testid={`odoo-widget-date-${field.name}`}>
        <span>2026-09-01</span>
        <span className="odoo-widget-date-icon" aria-hidden />
      </span>
    );
  }

  if (ttype === "datetime" || widget === "datetime") {
    return (
      <span className="odoo-widget-date" data-testid={`odoo-widget-datetime-${field.name}`}>
        <span>2026-09-01 09:00</span>
        <span className="odoo-widget-date-icon" aria-hidden />
      </span>
    );
  }

  if (ttype === "monetary" || widget === "monetary") {
    return (
      <span className="odoo-widget-monetary" data-testid={`odoo-widget-monetary-${field.name}`}>
        <span className="odoo-widget-currency">USD</span>
        <span className="odoo-widget-amount">0.00</span>
      </span>
    );
  }

  if (ttype === "float" || ttype === "integer") {
    return (
      <span className="odoo-widget-number" data-testid={`odoo-widget-number-${field.name}`}>
        {ttype === "integer" ? "0" : "0.00"}
      </span>
    );
  }

  if (ttype === "html" || widget === "html") {
    return (
      <span className="odoo-widget-html" data-testid={`odoo-widget-html-${field.name}`}>
        Rich text body…
      </span>
    );
  }

  if (ttype === "text") {
    return (
      <span className="odoo-widget-text" data-testid={`odoo-widget-text-${field.name}`}>
        {isStockPlaceholder(field) ? "" : "Multiline notes…"}
      </span>
    );
  }

  const sample = isStockPlaceholder(field)
    ? field.name === "_host_name"
      ? "Sample contact"
      : ""
    : field.name === "x_name" || field.name.endsWith("_name")
      ? "Sample record"
      : field.string || field.name;

  // Never render literal False/True/checkbox as the visible value.
  const safe =
    typeof sample === "string" &&
    ["false", "true", "checkbox", "boolean"].includes(sample.toLowerCase())
      ? ""
      : sample;

  return (
    <span className="odoo-widget-char" data-testid={`odoo-widget-char-${field.name}`}>
      {safe}
    </span>
  );
}

export function OdooField({ field, highlighted, onClick }: OdooFieldProps) {
  const stock = isStockPlaceholder(field);
  const requiredMark = field.required ? (
    <span className="odoo-field-required" aria-hidden>
      *
    </span>
  ) : null;

  const body = (
    <>
      <div className="odoo-field-label">
        {field.string || field.name}
        {requiredMark}
      </div>
      <div
        className={`odoo-field-value ${highlighted ? "field-highlight" : ""} ${stock ? "is-stock" : ""}`}
        data-testid={`odoo-field-${field.name}`}
        data-ttype={field.ttype || "char"}
      >
        <WidgetBody field={field} />
      </div>
    </>
  );

  const rowClass = `odoo-field-row ${stock ? "is-stock" : ""} ${highlighted ? "is-extension" : ""}`;

  if (onClick) {
    return (
      <button
        type="button"
        className={`${rowClass} w-full text-left`}
        onClick={onClick}
        aria-label={`${field.string || field.name} ${field.name}`}
      >
        {body}
      </button>
    );
  }

  return <div className={rowClass}>{body}</div>;
}
