"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { RelativeTime } from "@/components/ui/craft";
import type { SnapshotRow } from "@/lib/api";

const REVERSIBLE: Record<string, string> = {
  yes: "Can be undone",
  partial: "Partly undoable",
  no: "Record only",
};

/**
 * A4 — the one History, scoped to a page. Every page that writes shows this same panel
 * (same rows, same Undo through the shared snapshot rollback) and links to the full History.
 */
export function PageHistory({
  connectionId,
  snapshots,
  types,
  busy,
  onRollback,
  testId,
  rowTestId,
  emptyText,
  className = "mt-8 space-y-3",
  limit = 8,
}: {
  connectionId: string;
  snapshots: SnapshotRow[];
  /** Snapshot resource types this page owns. */
  types: ReadonlySet<string>;
  busy?: boolean;
  onRollback: (snapshotId: string) => void;
  testId: string;
  rowTestId?: (id: string) => string;
  emptyText: string;
  className?: string;
  limit?: number;
}) {
  const rows = snapshots.filter((s) => types.has(s.resource_type));
  return (
    <section className={className} data-testid={testId} aria-labelledby={`${testId}-title`}>
      <div className="flex items-baseline justify-between gap-3">
        <h2 id={`${testId}-title`} className="text-sm font-semibold text-ink">
          History
        </h2>
        <Link href={`/connections/${connectionId}/journal`} className="text-xs text-accent hover:underline">
          See all History
        </Link>
      </div>
      {rows.length === 0 ? (
        <p className="text-sm text-muted">{emptyText}</p>
      ) : (
        <ul className="space-y-2">
          {rows.slice(0, limit).map((s) => (
            <li
              key={s.id}
              data-testid={rowTestId?.(s.id)}
              className="hairline flex flex-wrap items-center justify-between gap-3 rounded-md p-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm text-ink">{s.label}</p>
                <p className="text-xs text-muted">
                  {REVERSIBLE[s.reversible] ?? s.reversible}
                  {s.created_at ? (
                    <>
                      {" · "}
                      <RelativeTime value={s.created_at} />
                    </>
                  ) : null}
                </p>
              </div>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                disabled={busy || s.reversible === "no"}
                onClick={() => onRollback(s.id)}
              >
                Undo
              </Button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
