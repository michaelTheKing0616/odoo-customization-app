"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { IconAccess } from "@/components/ui/icons";
import { crudLetters, filterByQuery } from "@/lib/accessForm";
import type { RecordRuleRow } from "@/lib/api";
import { cn } from "@/lib/cn";

type RecordRulesListProps = {
  rows: RecordRuleRow[];
  loading?: boolean;
  selectedId: number | null;
  query: string;
  onQueryChange: (query: string) => void;
  onSelect: (row: RecordRuleRow) => void;
  onCreate: () => void;
};

export function RecordRulesList({
  rows,
  loading,
  selectedId,
  query,
  onQueryChange,
  onSelect,
  onCreate,
}: RecordRulesListProps) {
  const filtered = filterByQuery(rows, query, (row) => `${row.name} ${row.domain_force ?? ""}`);

  return (
    <div className="space-y-3" data-testid="access-rules-list">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Record rules</h2>
        <Button type="button" variant="secondary" size="sm" onClick={onCreate} data-testid="access-new-rule">
          New rule
        </Button>
      </div>
      <input
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder="Filter by name or domain"
        aria-label="Filter record rules"
        data-testid="access-rules-filter"
        className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 text-sm text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
      />
      {loading ? (
        <div className="space-y-2" data-testid="access-rules-loading">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<IconAccess className="h-5 w-5" />}
          title={rows.length === 0 ? "No record rules yet" : "No matching rules"}
          description={
            rows.length === 0
              ? "Record rules filter which rows a group can see or change. Domain uses the same builder as Automations."
              : "Try a different filter, or create a new record rule."
          }
          action={
            <Button type="button" variant="primary" size="sm" onClick={onCreate}>
              Create rule
            </Button>
          }
        />
      ) : (
        <ul className="space-y-2">
          {filtered.map((row) => {
            const selected = selectedId === row.id;
            const global = row.global || (row.group_ids ?? []).length === 0;
            return (
              <li key={row.id}>
                <Card
                  role="button"
                  tabIndex={0}
                  aria-pressed={selected}
                  data-testid={`access-rule-row-${row.id}`}
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
                        {row.domain_force || "[]"}
                      </p>
                    </div>
                    <Badge variant={global ? "warning" : "default"}>
                      {global ? "Global" : crudLetters(row)}
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
