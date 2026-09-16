"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { IconAutomations } from "@/components/ui/icons";
import { EMPTY_STATES } from "@/lib/copy-guide";
import { triggerLabel } from "@/lib/automationForm";
import type { AutomationRow } from "@/lib/api";
import { cn } from "@/lib/cn";

type AutomationsListProps = {
  rows: AutomationRow[];
  loading?: boolean;
  selectedId: number | null;
  modelFilter: string;
  query: string;
  onQueryChange: (query: string) => void;
  onSelect: (row: AutomationRow) => void;
  onCreate: () => void;
};

export function AutomationsList({
  rows,
  loading,
  selectedId,
  modelFilter,
  query,
  onQueryChange,
  onSelect,
  onCreate,
}: AutomationsListProps) {
  const filtered = rows.filter((row) => {
    if (modelFilter && row.model !== modelFilter) return false;
    const hay = `${row.name} ${row.model} ${row.trigger}`.toLowerCase();
    return hay.includes(query.trim().toLowerCase());
  });

  return (
    <div className="space-y-3" data-testid="automations-list">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-ui-title font-semibold text-ink">Rules</h2>
        <Button type="button" variant="secondary" size="sm" onClick={onCreate}>
          New automation
        </Button>
      </div>
      <input
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder="Filter by name or model"
        aria-label="Filter automations"
        data-testid="automations-list-filter"
        className="h-row w-full rounded-md border border-border-subtle bg-surface px-3 text-ui-body text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
      />
      {modelFilter ? (
        <p className="text-xs text-muted" data-testid="automations-model-filter">
          Showing {modelFilter}
        </p>
      ) : null}
      {loading ? (
        <div className="space-y-2" data-testid="automations-list-loading">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<IconAutomations className="h-5 w-5" />}
          title={rows.length === 0 ? "No automations yet" : "No matching rules"}
          description={
            rows.length === 0
              ? EMPTY_STATES.automations
              : "Try a different filter, or create a new automation."
          }
          action={
            <Button type="button" variant="primary" size="sm" onClick={onCreate}>
              Create automation
            </Button>
          }
        />
      ) : (
        <ul className="space-y-2">
          {filtered.map((row) => {
            const selected = selectedId === row.id;
            return (
              <li key={row.id}>
                <Card
                  role="button"
                  tabIndex={0}
                  aria-pressed={selected}
                  data-testid={`automation-row-${row.id}`}
                  onClick={() => onSelect(row)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect(row);
                    }
                  }}
                  className={cn(
                    "cursor-pointer p-3 transition-colors hover:bg-surface-muted",
                    selected && "border-accent bg-accent-subtle",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-ink">{row.name}</p>
                      <p className="mt-0.5 truncate font-mono text-[11px] text-muted">
                        {row.model}
                      </p>
                    </div>
                    <Badge variant={row.active ? "success" : "default"}>
                      {row.active ? "Active" : "Inactive"}
                    </Badge>
                  </div>
                  <p className="mt-2 text-xs text-muted">{triggerLabel(row.trigger)}</p>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
