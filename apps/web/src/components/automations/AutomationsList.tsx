"use client";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/layout-primitives";
import { automationsEmptyGuide, triggerLabel, type AutomationStarter } from "@/lib/automationForm";
import type { AutomationRow } from "@/lib/api";
import { AutomationsStateGuide } from "./AutomationsStateGuide";

type AutomationsListProps = {
  rows: AutomationRow[];
  loading?: boolean;
  selectedId: number | null;
  modelFilter: string;
  query: string;
  onQueryChange: (query: string) => void;
  onSelect: (row: AutomationRow) => void;
  onCreate: () => void;
  starters?: AutomationStarter[];
  onStarter?: (s: AutomationStarter) => void;
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
  starters = [],
  onStarter,
}: AutomationsListProps) {
  const filtered = rows.filter((row) => {
    if (modelFilter && row.model !== modelFilter) return false;
    const hay = `${row.name} ${row.model} ${row.trigger}`.toLowerCase();
    return hay.includes(query.trim().toLowerCase());
  });
  const emptyGuide = automationsEmptyGuide(rows.length > 0 || Boolean(query.trim()), query.trim());

  return (
    <div className="space-y-3" data-testid="automations-list">
      <div className="au-list-head">
        <h2 className="au-list-title">Rules</h2>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={onCreate}
          data-testid="automations-new"
        >
          New automation
        </Button>
      </div>
      {rows.length > 0 || query ? (
        <input
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Filter by name or model"
          aria-label="Filter automations"
          data-testid="automations-list-filter"
          className="au-search"
        />
      ) : null}
      {modelFilter ? (
        <p className="text-ui-meta text-muted" data-testid="automations-model-filter">
          Showing {modelFilter}
        </p>
      ) : null}
      {loading ? (
        <div className="space-y-2" data-testid="automations-list-loading">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : filtered.length === 0 ? (
        <AutomationsStateGuide
          testId="automations-empty"
          guide={emptyGuide}
          actions={
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={onCreate}
              data-testid="automations-empty-create"
            >
              Create automation
            </Button>
          }
        >
          {!rows.length && !query.trim() && onStarter && starters.length ? (
            <div className="au-starters" data-testid="automations-starters">
              <p className="text-ui-meta text-muted">Or start from your own data:</p>
              {starters.map((st) => (
                <Button key={st.model + st.trigger} type="button" variant="secondary" size="sm" onClick={() => onStarter(st)}>
                  {st.label}
                </Button>
              ))}
            </div>
          ) : null}
        </AutomationsStateGuide>
      ) : (
        <ul className="au-list">
          {filtered.map((row) => {
            const selected = selectedId === row.id;
            return (
              <li key={row.id}>
                <div
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
                  className="au-list-row"
                >
                  <div className="min-w-0">
                    <p className="au-list-name">{row.name}</p>
                    <p className="au-list-meta is-mono">{row.model}</p>
                    <p className="au-list-meta">{triggerLabel(row.trigger)}</p>
                  </div>
                  <Badge variant={row.active ? "success" : "default"}>
                    {row.active ? "Active" : "Inactive"}
                  </Badge>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
