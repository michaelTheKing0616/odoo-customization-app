"use client";

import type { FieldRow } from "@/lib/api";

type ReportFieldPickerProps = {
  id?: string;
  label: string;
  value: string;
  fields: FieldRow[];
  disabled?: boolean;
  allowEmpty?: boolean;
  emptyLabel?: string;
  /** Extra static options (e.g. company_logo for images). */
  extraOptions?: Array<{ value: string; label: string }>;
  testId?: string;
  onChange: (value: string) => void;
};

/**
 * Schema-fed field picker for PDF-04. Options come only from listFields /
 * fields_get for the bound (or related) model — never free-text inventing.
 */
export function ReportFieldPicker({
  id,
  label,
  value,
  fields,
  disabled,
  allowEmpty = false,
  emptyLabel = "— pick a field —",
  extraOptions = [],
  testId,
  onChange,
}: ReportFieldPickerProps) {
  const names = new Set(fields.map((f) => f.name));
  for (const extra of extraOptions) names.add(extra.value);
  const orphan = value && !names.has(value) ? value : null;

  return (
    <label className="block text-xs">
      {label}
      <select
        id={id}
        data-testid={testId}
        disabled={disabled}
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        className="mt-1 w-full border border-border-subtle bg-surface px-2 py-1 font-mono text-xs"
      >
        {allowEmpty ? <option value="">{emptyLabel}</option> : null}
        {extraOptions.map((opt) => (
          <option key={`extra-${opt.value}`} value={opt.value}>
            {opt.label}
          </option>
        ))}
        {orphan ? (
          <option value={orphan}>
            {orphan} (not on model — pick another)
          </option>
        ) : null}
        {fields.map((f) => (
          <option key={f.name} value={f.name}>
            {f.name}
            {f.field_description ? ` — ${f.field_description}` : ""}
            {f.ttype ? ` (${f.ttype})` : ""}
          </option>
        ))}
      </select>
    </label>
  );
}
