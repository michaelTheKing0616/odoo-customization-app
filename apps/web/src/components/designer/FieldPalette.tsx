"use client";

import { useMemo, useState } from "react";
import { attachDragGhost, setPaletteDragData } from "@/lib/designer-dnd";

/** Palette of Odoo fields for Designer drag-drop. */

export type PaletteField = {
  name: string;
  ttype: string;
  label?: string;
};

export function FieldPalette({
  fields,
  onDragStart,
}: {
  fields: PaletteField[];
  onDragStart?: (name: string) => void;
}) {
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return fields;
    return fields.filter(
      (f) =>
        f.name.toLowerCase().includes(q) ||
        (f.label || "").toLowerCase().includes(q) ||
        f.ttype.toLowerCase().includes(q),
    );
  }, [fields, query]);

  return (
    <div className="odoo-sheet max-h-[min(28rem,70vh)] overflow-auto p-2" data-testid="designer-field-palette">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--odoo-muted)]">
        Fields
      </p>
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Filter fields"
        aria-label="Filter fields"
        className="mb-2 w-full rounded-md border border-[var(--odoo-border)] bg-surface px-2 py-1.5 text-xs text-ink"
      />
      <ul className="space-y-1" data-testid="designer-field-list">
        {filtered.map((f) => (
          <li
            key={f.name}
            draggable
            onDragStart={(e) => {
              setPaletteDragData(e.dataTransfer, f.name);
              attachDragGhost(e.dataTransfer, f.label || f.name, e.currentTarget);
              onDragStart?.(f.name);
            }}
            className="cursor-grab rounded-md border border-[var(--odoo-border)] bg-surface px-2 py-1.5 text-xs shadow-subtle active:cursor-grabbing"
            data-testid={`palette-field-${f.name}`}
          >
            <span className="font-medium text-[var(--odoo-sheet-fg)]">{f.label || f.name}</span>
            <span className="ml-2 font-mono text-[var(--odoo-primary)]">{f.name}</span>
            <span className="ml-2 text-[var(--odoo-muted)]">{f.ttype}</span>
          </li>
        ))}
        {filtered.length === 0 && (
          <li className="text-xs text-[var(--odoo-muted)]">
            {fields.length === 0 ? "Load a model to populate." : "No fields match."}
          </li>
        )}
      </ul>
    </div>
  );
}
