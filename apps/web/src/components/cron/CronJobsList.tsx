"use client";

import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/layout-primitives";
import type { CronRowOut } from "@/lib/api";
import {
  DISABLE_CTA,
  ENABLE_CTA,
  emptyCronGuide,
  formatCronNextRun,
  intervalLabel,
  type CronIntervalType,
} from "@/lib/cronManagerScreen";
import { CronStateGuide } from "./CronStateGuide";

export function CronJobsList({
  rows,
  loading,
  selected,
  busy,
  timeZone,
  zoneLabel,
  onToggleSelected,
  onToggleActive,
  onRefresh,
}: {
  rows: CronRowOut[];
  loading?: boolean;
  selected: Set<number>;
  busy: boolean;
  timeZone: string;
  zoneLabel: string;
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
      <CronStateGuide
        testId="cron-empty-guide"
        tone="accent"
        guide={emptyCronGuide()}
        actions={
          <Button type="button" variant="secondary" size="sm" disabled={busy} onClick={onRefresh}>
            Refresh list
          </Button>
        }
      />
    );
  }

  return (
    <div className="cr-table-wrap" data-testid="cron-jobs-list">
      <table className="cr-table">
        <thead>
          <tr>
            <th scope="col">Pick</th>
            <th scope="col">Description</th>
            <th scope="col">Model</th>
            <th scope="col">Schedule</th>
            <th scope="col">Next run</th>
            <th scope="col">Active</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const interval =
              row.interval_number != null && row.interval_type
                ? intervalLabel(row.interval_number, row.interval_type as CronIntervalType)
                : null;
            const nextLabel = formatCronNextRun(row.nextcall, timeZone);
            return (
              <tr key={row.id} data-testid={`cron-row-${row.id}`}>
                <td>
                  <input
                    type="checkbox"
                    className="size-4 accent-[var(--accent)]"
                    checked={selected.has(row.id)}
                    onChange={() => onToggleSelected(row.id)}
                    aria-label={`Select ${row.name}`}
                    disabled={busy}
                  />
                </td>
                <td>
                  <div className="cr-row-name">{row.name}</div>
                  {row.description ? <div className="cr-row-meta">{row.description}</div> : null}
                </td>
                <td className="font-mono text-xs">{row.model_name || "-"}</td>
                <td className="text-xs text-[var(--muted)]">{interval || "-"}</td>
                <td>
                  <div className="tabular-nums text-xs text-ink">{nextLabel}</div>
                  <div className="cr-row-meta">{zoneLabel}</div>
                </td>
                <td>
                  <button
                    type="button"
                    className="cr-status"
                    data-active={row.active ? "true" : "false"}
                    data-testid={`cron-toggle-${row.id}`}
                    disabled={busy}
                    onClick={() => onToggleActive(row)}
                    aria-pressed={row.active}
                  >
                    {row.active ? DISABLE_CTA : ENABLE_CTA}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
