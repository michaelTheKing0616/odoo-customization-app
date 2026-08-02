"use client";

import { useEffect, useState } from "react";

export type SelectionRow = { value: string; label: string };

/** Serialize rows to Odoo selection string e.g. `[('a','A'),('b','B')]`. */
export function selectionRowsToString(rows: SelectionRow[]): string {
  const parts = rows
    .map((r) => ({
      value: r.value.trim(),
      label: (r.label.trim() || r.value.trim()).trim(),
    }))
    .filter((r) => r.value);
  return "[" + parts.map((r) => `(${JSON.stringify(r.value)},${JSON.stringify(r.label)})`).join(",") + "]";
}

/** Parse Odoo-ish selection or "value,Label" lines into rows. */
export function parseSelectionInput(text: string): SelectionRow[] {
  const trimmed = text.trim();
  if (trimmed.startsWith("[") && trimmed.includes("(")) {
    const rows: SelectionRow[] = [];
    const re = /\(\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]*)['"]\s*\)/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(trimmed))) {
      rows.push({ value: m[1], label: m[2] || m[1] });
    }
    if (rows.length) return rows;
  }
  return trimmed
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [value, ...rest] = line.split(",");
      return { value: value.trim(), label: (rest.join(",") || value).trim() };
    });
}

type Props = {
  value: SelectionRow[];
  onChange: (rows: SelectionRow[]) => void;
  className?: string;
};

export function SelectionEditor({ value, onChange, className }: Props) {
  const rows = value.length ? value : [{ value: "", label: "" }];

  function updateRow(index: number, patch: Partial<SelectionRow>) {
    const next = rows.map((r, i) => (i === index ? { ...r, ...patch } : r));
    onChange(next);
  }

  function addRow() {
    onChange([...rows, { value: "", label: "" }]);
  }

  function removeRow(index: number) {
    const next = rows.filter((_, i) => i !== index);
    onChange(next.length ? next : [{ value: "", label: "" }]);
  }

  return (
    <div className={className ?? "space-y-2"}>
      <p className="text-xs text-[#8f7a88]">
        Selection options →{" "}
        <code className="text-[#c9a9c0]">{selectionRowsToString(rows)}</code>
      </p>
      {rows.map((row, i) => (
        <div key={i} className="flex flex-wrap gap-2">
          <input
            value={row.value}
            onChange={(e) => updateRow(i, { value: e.target.value })}
            placeholder="value"
            className="min-w-[7rem] flex-1 border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 font-mono text-sm"
          />
          <input
            value={row.label}
            onChange={(e) => updateRow(i, { label: e.target.value })}
            placeholder="Label"
            className="min-w-[7rem] flex-1 border border-[#3d2a38] bg-[#0c090b] px-2 py-1.5 text-sm"
          />
          <button
            type="button"
            onClick={() => removeRow(i)}
            className="text-xs text-[#f0a8a0] hover:underline"
          >
            Remove
          </button>
        </div>
      ))}
      <button
        type="button"
        onClick={addRow}
        className="text-xs text-[#c9a9c0] hover:underline"
      >
        + Add option
      </button>
    </div>
  );
}

/** Controlled helper: keep parent string in sync with row editor. */
export function SelectionEditorFromString({
  value,
  onChange,
}: {
  value: string;
  onChange: (selectionString: string, rows: SelectionRow[]) => void;
}) {
  const [rows, setRows] = useState<SelectionRow[]>(() =>
    parseSelectionInput(value || "draft,Draft\ndone,Done"),
  );

  useEffect(() => {
    // External reset only when empty → seed
    if (!value.trim() && rows.every((r) => !r.value)) {
      setRows([{ value: "draft", label: "Draft" }, { value: "done", label: "Done" }]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  return (
    <SelectionEditor
      value={rows}
      onChange={(next) => {
        setRows(next);
        onChange(selectionRowsToString(next), next);
      }}
    />
  );
}
