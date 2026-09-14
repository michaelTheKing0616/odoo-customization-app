"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { IconAccess } from "@/components/ui/icons";
import { EMPTY_STATES } from "@/lib/copy-guide";
import { crudLetters, filterByQuery } from "@/lib/accessForm";
import type { AccessRightRow } from "@/lib/api";
import { cn } from "@/lib/cn";

type AccessRightsListProps = {
  rows: AccessRightRow[];
  loading?: boolean;
  selectedId: number | null;
  query: string;
  onQueryChange: (query: string) => void;
  onSelect: (row: AccessRightRow) => void;
  onCreate: () => void;
};

export function AccessRightsList({
  rows,
  loading,
  selectedId,
  query,
  onQueryChange,
  onSelect,
  onCreate,
}: AccessRightsListProps) {
  const filtered = filterByQuery(rows, query, (row) => `${row.name} ${row.group_name ?? ""}`);

  return (
    <div className="space-y-3" data-testid="access-rights-list">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Access rights</h2>
        <Button type="button" variant="secondary" size="sm" onClick={onCreate} data-testid="access-new-right">
          New access
        </Button>
      </div>
      <input
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder="Filter by name or group"
        aria-label="Filter access rights"
        data-testid="access-rights-filter"
        className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 text-sm text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
      />
      {loading ? (
        <div className="space-y-2" data-testid="access-rights-loading">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<IconAccess className="h-5 w-5" />}
          title={rows.length === 0 ? "No access lines yet" : "No matching access lines"}
          description={
            rows.length === 0
              ? EMPTY_STATES.access
              : "Try a different filter, or create a new access line."
          }
          action={
            <Button type="button" variant="primary" size="sm" onClick={onCreate}>
              Create access
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
                  data-testid={`access-right-row-${row.id}`}
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
                      <p className="mt-0.5 truncate text-xs text-muted">
                        {row.group_name ?? "All users"}
                      </p>
                    </div>
                    <Badge variant={row.group_id ? "default" : "warning"}>
                      {crudLetters(row)}
                    </Badge>
                  </div>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
