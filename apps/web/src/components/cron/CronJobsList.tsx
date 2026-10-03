"use client";

import { Button } from "@/components/ui/Button";
import { EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import type { CronRowOut } from "@/lib/api";

export function CronJobsList({
  rows,
  loading,
  selected,
  busy,
  onToggleSelected,
  onToggleActive,
  onRefresh,
}: {
  rows: CronRowOut[];
  loading?: boolean;
  selected: Set<number>;
  busy: boolean;
  onToggleSelected: (id: number) => void;
  onToggleActive: (row: CronRowOut) => void;
  onRefresh: () => void;
}) {
  if (loading) {
    return (
      <div className="space-y-2" data-testid="cron-jobs-list-loading">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-full" />
      </div>
    );
  }

  if (!rows.length) {
    return (
      <EmptyState
        title="No scheduled actions match"
        description="Broaden the filter or create a cron below to schedule server actions on this connection."
        action={
          <Button type="button" variant="secondary" size="sm" disabled={busy} onClick={onRefresh}>
            Refresh list
          </Button>
        }
      />
    );
  }

  return (
    <div className="overflow-x-auto" data-testid="cron-jobs-list">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--odoo-border)] text-[var(--odoo-muted)]">
            <th className="py-2 pr-2">Pick</th>
            <th className="py-2 pr-2">Description</th>
            <th className="py-2 pr-2">Model</th>
            <th className="py-2 pr-2">Active</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-b border-[var(--odoo-border)]/60">
              <td className="py-2 pr-2 align-top">
                <input
                  type="checkbox"
                  checked={selected.has(row.id)}
                  onChange={() => onToggleSelected(row.id)}
                />
              </td>
              <td className="py-2 pr-2 align-top">
                <div className="font-medium">{row.name}</div>
                <div className="text-xs text-[var(--odoo-muted)]">{row.description}</div>
                {row.nextcall ? (
                  <div className="text-xs text-[var(--odoo-muted)]">Next: {row.nextcall}</div>
                ) : null}
              </td>
              <td className="py-2 pr-2 align-top font-mono text-xs">{row.model_name || "—"}</td>
              <td className="py-2 pr-2 align-top">
                <button
                  type="button"
                  className="text-xs underline"
                  disabled={busy}
                  onClick={() => onToggleActive(row)}
                >
                  {row.active ? "Active" : "Inactive"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
