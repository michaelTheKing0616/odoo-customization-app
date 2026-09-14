"use client";

import type { ModuleSpecDoc } from "@/lib/modulespec-types";
import { relationalFields } from "@/lib/modulespec-journey";

type ModuleSpecRelationsPanelProps = {
  spec: ModuleSpecDoc;
  onSelectModel?: (model: string) => void;
};

export function ModuleSpecRelationsPanel({ spec, onSelectModel }: ModuleSpecRelationsPanelProps) {
  const rows = relationalFields(spec);
  return (
    <div className="space-y-3" data-testid="modulespec-relations">
      <h3 className="text-sm font-semibold text-ink">Relations</h3>
      <p className="text-sm text-muted">
        Derived from many2one, one2many, and many2many fields. Missing targets block Generate UI.
      </p>
      {rows.length === 0 ? (
        <p className="text-sm text-muted">No relational fields yet.</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((row) => {
            const target = String(row.field.relation || "").trim();
            return (
              <li
                key={`${row.model}.${row.field.name}`}
                className="flex flex-wrap items-center gap-2 rounded-md border border-border-subtle bg-surface-raised px-3 py-2"
              >
                <button
                  type="button"
                  className="font-mono text-xs text-ink hover:underline"
                  onClick={() => onSelectModel?.(row.model)}
                >
                  {row.model}.{row.field.name}
                </button>
                <span className="text-xs text-muted">{row.field.ttype}</span>
                <span className={target ? "font-mono text-xs text-ink" : "text-xs text-danger"}>
                  {target ? `→ ${target}` : "missing target"}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
