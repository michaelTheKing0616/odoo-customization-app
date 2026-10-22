"use client";

import type { RecField, RecRow } from "@/lib/api/suite";

/** Touch 80: a board needs a stage or state; prefer stage_id, then state, then any choice field. */
export function pickBoardField(fields: RecField[]): RecField | null {
  return (
    fields.find((f) => f.name === "stage_id" && f.type === "many2one") ??
    fields.find((f) => f.name === "state" && f.type === "selection") ??
    null
  );
}

export function boardKey(v: unknown, field: RecField): { key: string; label: string } {
  if (Array.isArray(v)) return { key: String(v[0]), label: String(v[1] ?? v[0]) };
  if (v && typeof v === "object" && "id" in v) {
    const o = v as { id: unknown; display_name?: unknown; name?: unknown };
    return { key: String(o.id), label: String(o.display_name ?? o.name ?? o.id) };
  }
  if (v === false || v === null || v === undefined || v === "") return { key: "", label: "None" };
  const c = field.choices.find((x) => x.value === v);
  return { key: String(v), label: c?.label ?? String(v) };
}

export function groupForBoard(rows: RecRow[], field: RecField) {
  const cols = new Map<string, { label: string; rows: RecRow[] }>();
  if (field.type === "selection") for (const c of field.choices) cols.set(c.value, { label: c.label, rows: [] });
  for (const r of rows) {
    const k = boardKey(r[field.name], field);
    if (!cols.has(k.key)) cols.set(k.key, { label: k.label, rows: [] });
    cols.get(k.key)!.rows.push(r);
  }
  return [...cols.entries()].map(([key, v]) => ({ key, ...v }));
}

export function RecordBoard({ rows, field, selected, onToggle }: { rows: RecRow[]; field: RecField; selected: Set<number>; onToggle: (id: number, on: boolean) => void }) {
  const cols = groupForBoard(rows, field);
  return (
    <div className="rec-board" data-testid="rec-board" aria-label={`Board by ${field.label}. Shows this page's records.`}>
      {cols.map((c) => (
        <section key={c.key} className="rec-board-col" aria-label={`${c.label}, ${c.rows.length}`}>
          <h3 className="rec-board-head">{c.label} <span className="text-muted">{c.rows.length}</span></h3>
          <ul>
            {c.rows.map((r) => (
              <li key={r.id} className="rec-board-card" aria-selected={selected.has(r.id)} data-testid={`rec-card-${r.id}`}>
                <label>
                  <input type="checkbox" aria-label={`Select ${r.display_name}`} checked={selected.has(r.id)} onChange={(e) => onToggle(r.id, e.target.checked)} />
                  <span>{r.display_name}</span>
                </label>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
