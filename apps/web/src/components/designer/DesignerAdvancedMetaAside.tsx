"use client";

import type { SnapshotRow } from "@/lib/api";

export type DesignerAdvancedMetaAsideProps = {
  arch: string;
  snapshots: SnapshotRow[];
  busy: boolean;
  onRefreshSnapshots: () => void;
  onRollback: (snapshotId: string) => void;
};

/** Right column under Advanced layout — arch preview + published checkpoints. */
export function DesignerAdvancedMetaAside({
  arch,
  snapshots,
  busy,
  onRefreshSnapshots,
  onRollback,
}: DesignerAdvancedMetaAsideProps) {
  return (
    <aside className="space-y-4" data-testid="designer-advanced-meta-aside">
      <p className="text-xs text-muted">
        Field properties and XPath inherit live in the right-hand Properties and Advanced tabs.
      </p>

      <div className="border border-border-subtle bg-surface p-4">
        <p className="text-xs uppercase tracking-wide text-muted">Generated arch</p>
        <pre className="mt-3 max-h-48 overflow-auto text-xs text-muted">{arch || "—"}</pre>
      </div>

      <div className="border border-border-subtle bg-surface-muted/70 p-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs uppercase tracking-wide text-muted">Published checkpoints</p>
          <button
            type="button"
            className="text-xs text-muted hover:underline"
            onClick={() => onRefreshSnapshots()}
          >
            Refresh
          </button>
        </div>
        <ul className="mt-3 max-h-48 space-y-2 overflow-auto text-xs">
          {snapshots.length === 0 && (
            <li className="text-muted">No published checkpoints yet. Save to Odoo creates one.</li>
          )}
          {snapshots.map((s) => (
            <li
              key={s.id}
              className="flex items-start justify-between gap-2 border border-border-subtle px-2 py-1.5"
            >
              <div>
                <p className="text-ink">{s.label}</p>
                <p className="text-muted">
                  {s.reversible} · {s.created_at}
                </p>
              </div>
              <button
                type="button"
                disabled={busy || s.reversible === "no"}
                onClick={() => onRollback(s.id)}
                className="shrink-0 border border-border-subtle px-2 py-0.5 text-muted disabled:opacity-40"
              >
                Restore
              </button>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
