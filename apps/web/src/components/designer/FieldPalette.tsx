"use client";

/** Palette of Odoo fields for Designer drag-drop (Odoo-coloured chrome). */

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
  return (
    <div className="odoo-sheet max-h-96 overflow-auto p-2">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--odoo-muted)]">
        Fields
      </p>
      <ul className="space-y-1">
        {fields.map((f) => (
          <li
            key={f.name}
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData("text/odoo-field", f.name);
              onDragStart?.(f.name);
            }}
            className="cursor-grab border border-[var(--odoo-border)] bg-white px-2 py-1 text-xs active:cursor-grabbing"
          >
            <span className="font-mono text-[var(--odoo-primary)]">{f.name}</span>
            <span className="ml-2 text-[var(--odoo-muted)]">{f.ttype}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
