"use client";

/**
 * Odoo-familiar kanban card preview for the View Designer.
 * Structural preview — Open-in-Odoo remains authoritative.
 * Labels (nolabel) are not in our kanban arch helpers yet — values only.
 */

export type KanbanCardField = {
  id: string;
  name: string;
  string?: string;
};

export type KanbanCardPreviewProps = {
  title: string;
  groupBy?: string | null;
  fields: KanbanCardField[];
  selectedFieldId?: string | null;
  onSelectField?: (fieldId: string) => void;
  onMoveField?: (fieldId: string, dir: -1 | 1) => void;
  onRemoveField?: (fieldId: string) => void;
  onDropFieldName?: (fieldName: string) => void;
};

export function KanbanCardPreview({
  title,
  groupBy,
  fields,
  selectedFieldId,
  onSelectField,
  onMoveField,
  onRemoveField,
  onDropFieldName,
}: KanbanCardPreviewProps) {
  const columns = groupBy
    ? [
        { key: "a", label: `${groupBy} · A` },
        { key: "b", label: `${groupBy} · B` },
      ]
    : [{ key: "all", label: "All records" }];

  return (
    <div
      className="odoo-kanban-canvas overflow-hidden shadow-sm"
      data-testid="kanban-card-preview"
    >
      <div className="odoo-form-header flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold text-[var(--odoo-primary)]">
          {title}
        </span>
        {groupBy ? (
          <span
            className="rounded bg-[var(--odoo-primary)] px-2 py-0.5 text-xs text-white"
            data-testid="kanban-groupby-chip"
          >
            Group by · {groupBy}
          </span>
        ) : (
          <span className="rounded border border-[var(--odoo-border)] bg-white px-2 py-0.5 text-xs text-[var(--odoo-muted)]">
            No group-by
          </span>
        )}
      </div>

      <div
        className="flex gap-3 overflow-x-auto p-3"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const name = e.dataTransfer.getData("text/odoo-field");
          if (name && onDropFieldName) onDropFieldName(name);
        }}
      >
        {columns.map((col) => (
          <div
            key={col.key}
            className="min-w-[14rem] flex-1 rounded border border-[var(--odoo-border)] bg-[#f0eeeb]/60"
          >
            <div className="border-b border-[var(--odoo-border)] px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-[var(--odoo-muted)]">
              {col.label}
            </div>
            <div className="space-y-2 p-2">
              <div className="odoo-kanban-card border border-[var(--odoo-border)] bg-white p-2 shadow-sm">
                {fields.length === 0 ? (
                  <p className="text-xs text-[var(--odoo-muted)]">
                    Drop fields here to build the card
                  </p>
                ) : (
                  <ul className="space-y-1.5">
                    {fields.map((f, idx) => (
                      <li
                        key={f.id}
                        className={`rounded border px-2 py-1.5 ${
                          selectedFieldId === f.id
                            ? "border-[var(--odoo-primary)] bg-[#f5eef3]"
                            : "border-transparent hover:border-[var(--odoo-border)]"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <button
                            type="button"
                            className="min-w-0 flex-1 text-left"
                            onClick={() => onSelectField?.(f.id)}
                          >
                            <div className="truncate text-sm font-medium text-[var(--odoo-sheet-fg)]">
                              {f.string || f.name}
                            </div>
                            <div className="truncate font-mono text-[10px] text-[var(--odoo-muted)]">
                              {f.name}
                            </div>
                            {idx === 0 && (
                              <div className="mt-1 text-[11px] text-[var(--odoo-muted)]">
                                Sample value
                              </div>
                            )}
                          </button>
                          <span className="flex shrink-0 flex-col gap-0.5">
                            <button
                              type="button"
                              className="text-xs text-[var(--odoo-primary)] disabled:opacity-30"
                              disabled={idx === 0}
                              aria-label={`Move ${f.name} up`}
                              onClick={() => onMoveField?.(f.id, -1)}
                            >
                              ↑
                            </button>
                            <button
                              type="button"
                              className="text-xs text-[var(--odoo-primary)] disabled:opacity-30"
                              disabled={idx >= fields.length - 1}
                              aria-label={`Move ${f.name} down`}
                              onClick={() => onMoveField?.(f.id, 1)}
                            >
                              ↓
                            </button>
                            {onRemoveField && (
                              <button
                                type="button"
                                className="text-[10px] text-[var(--odoo-danger)]"
                                aria-label={`Remove ${f.name}`}
                                onClick={() => onRemoveField(f.id)}
                              >
                                ×
                              </button>
                            )}
                          </span>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              {col.key === columns[0]?.key && fields.length > 0 && (
                <div className="odoo-kanban-card border border-dashed border-[var(--odoo-border)] bg-white/70 p-2 opacity-60">
                  <div className="text-xs text-[var(--odoo-muted)]">
                    + more cards…
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-[var(--odoo-border)] bg-[#faf9f8] px-3 py-2 text-[11px] text-[var(--odoo-muted)]">
        Card field order matches saved kanban arch. Open in Odoo is authoritative.
      </div>
    </div>
  );
}
