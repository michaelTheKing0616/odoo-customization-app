"use client";

import { useMemo, useState } from "react";
import { attachDragGhost, setPaletteDragData } from "@/lib/designer-dnd";

/**
 * Palette of Odoo fields for Designer drag-drop.
 * UI-S-12 keeps Odoo Studio's clarity (fields listed by type) but denser:
 * type groups with counts, one filter that also matches the type.
 */

export type PaletteField = {
  name: string;
  ttype: string;
  label?: string;
};

export type PaletteTypeGroup = {
  id: "text" | "numbers" | "choice" | "dates" | "relations" | "files" | "other";
  label: string;
  ttypes: readonly string[];
};

export const PALETTE_TYPE_GROUPS: readonly PaletteTypeGroup[] = [
  { id: "text", label: "Text", ttypes: ["char", "text", "html"] },
  { id: "numbers", label: "Numbers", ttypes: ["integer", "float", "monetary"] },
  { id: "choice", label: "Choice", ttypes: ["selection", "boolean"] },
  { id: "dates", label: "Dates", ttypes: ["date", "datetime"] },
  {
    id: "relations",
    label: "Relations",
    ttypes: ["many2one", "one2many", "many2many", "many2one_reference", "reference"],
  },
  { id: "files", label: "Files", ttypes: ["binary", "image"] },
  { id: "other", label: "Other", ttypes: [] },
];

export function paletteTypeGroup(ttype: string): PaletteTypeGroup["id"] {
  const t = (ttype || "").toLowerCase();
  const hit = PALETTE_TYPE_GROUPS.find((g) => g.ttypes.includes(t));
  return hit ? hit.id : "other";
}

export function groupPaletteFields(
  fields: PaletteField[],
): Array<{ group: PaletteTypeGroup; fields: PaletteField[] }> {
  const buckets = new Map<PaletteTypeGroup["id"], PaletteField[]>();
  for (const f of fields) {
    const id = paletteTypeGroup(f.ttype);
    const list = buckets.get(id) ?? [];
    list.push(f);
    buckets.set(id, list);
  }
  return PALETTE_TYPE_GROUPS.filter((g) => buckets.has(g.id)).map((group) => ({
    group,
    fields: buckets.get(group.id) ?? [],
  }));
}

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
  const groups = useMemo(() => groupPaletteFields(filtered), [filtered]);

  return (
    <div className="designer-palette" data-testid="designer-field-palette">
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Filter by name or type"
        aria-label="Filter fields"
        className="designer-palette-search mb-4"
      />
      <div data-testid="designer-field-list">
        {groups.map(({ group, fields: groupFields }) => (
          <section
            key={group.id}
            className="designer-palette-group"
            aria-label={`${group.label} fields`}
            data-testid={`palette-group-${group.id}`}
          >
            <h3 className="designer-palette-heading">
              <span>{group.label}</span>
              <span className="designer-palette-count">{groupFields.length}</span>
            </h3>
            <ul className="space-y-px">
              {groupFields.map((f) => (
                <li
                  key={f.name}
                  draggable
                  onDragStart={(e) => {
                    setPaletteDragData(e.dataTransfer, f.name);
                    attachDragGhost(e.dataTransfer, f.label || f.name, e.currentTarget);
                    onDragStart?.(f.name);
                  }}
                  className="designer-palette-item"
                  data-testid={`palette-field-${f.name}`}
                  title={`Drag ${f.label || f.name} onto the canvas`}
                >
                  <span className="designer-palette-label">{f.label || f.name}</span>
                  <span className="designer-palette-name">{f.name}</span>
                  <span className="designer-palette-type">{f.ttype}</span>
                </li>
              ))}
            </ul>
          </section>
        ))}
        {filtered.length === 0 && (
          <p className="px-0.5 text-xs text-muted">
            {fields.length === 0
              ? "Load a model to list its fields."
              : `No fields match “${query.trim()}”.`}
          </p>
        )}
      </div>
    </div>
  );
}
