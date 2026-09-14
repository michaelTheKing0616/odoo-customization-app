"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { IconModels } from "@/components/ui/icons";
import { EMPTY_STATES } from "@/lib/copy-guide";
import { filterByQuery, isCustomTechnicalName } from "@/lib/builderForm";
import type { ModelRow } from "@/lib/api";
import { cn } from "@/lib/cn";

type BuilderModelsListProps = {
  rows: ModelRow[];
  loading?: boolean;
  selectedModel: string | null;
  query: string;
  onQueryChange: (query: string) => void;
  onSelect: (row: ModelRow) => void;
  onCreate: () => void;
  onOpenExisting: (model: string) => void;
};

export function BuilderModelsList({
  rows,
  loading,
  selectedModel,
  query,
  onQueryChange,
  onSelect,
  onCreate,
  onOpenExisting,
}: BuilderModelsListProps) {
  const filtered = filterByQuery(rows, query, (row) => `${row.name} ${row.model}`);
  const queryLooksLikeModel = query.trim().includes(".") || isCustomTechnicalName(query.trim());

  return (
    <div className="space-y-3" data-testid="builder-models-list">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Models</h2>
        <Button type="button" variant="secondary" size="sm" onClick={onCreate} data-testid="builder-new-model">
          New model
        </Button>
      </div>
      <input
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder="Filter custom models, or type a technical name"
        aria-label="Filter models"
        data-testid="builder-models-filter"
        className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 text-sm text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
        onKeyDown={(e) => {
          if (e.key === "Enter" && queryLooksLikeModel) {
            e.preventDefault();
            onOpenExisting(query.trim());
          }
        }}
      />
      {queryLooksLikeModel && filtered.length === 0 ? (
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="w-full justify-start font-mono text-xs"
          data-testid="builder-open-existing"
          onClick={() => onOpenExisting(query.trim())}
        >
          Open {query.trim()}
        </Button>
      ) : null}
      {loading ? (
        <div className="space-y-2" data-testid="builder-models-loading">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<IconModels className="h-5 w-5" />}
          title={rows.length === 0 ? "No custom models yet" : "No matching models"}
          description={
            rows.length === 0
              ? EMPTY_STATES.builder
              : "Try a different filter, create a new x_ model, or type a stock technical name to add fields there."
          }
          action={
            <Button type="button" variant="primary" size="sm" onClick={onCreate}>
              Create model
            </Button>
          }
        />
      ) : (
        <ul className="space-y-2">
          {filtered.map((row) => {
            const selected = selectedModel === row.model;
            return (
              <li key={row.id}>
                <Card
                  role="button"
                  tabIndex={0}
                  aria-pressed={selected}
                  data-testid={`builder-model-row-${row.model}`}
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
                      <p className="mt-0.5 truncate font-mono text-[11px] text-muted">{row.model}</p>
                    </div>
                    <Badge variant="default">Custom</Badge>
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
