"use client";

import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/layout-primitives";
import { AccessCrudLetters } from "@/components/access/AccessCrudLetters";
import { AccessStateGuide } from "@/components/access/AccessStateGuide";
import { filterByQuery } from "@/lib/accessForm";
import { accessEmptyGuide } from "@/lib/accessScreen";
import type { RecordRuleRow } from "@/lib/api";
import { Term } from "@/components/ui/Term";

type RecordRulesListProps = {
  rows: RecordRuleRow[];
  loading?: boolean;
  selectedId: number | null;
  query: string;
  onQueryChange: (query: string) => void;
  onSelect: (row: RecordRuleRow) => void;
  onCreate: () => void;
  model?: string;
};

export function RecordRulesList({
  rows,
  loading,
  selectedId,
  query,
  onQueryChange,
  onSelect,
  onCreate,
  model,
}: RecordRulesListProps) {
  const filtered = filterByQuery(rows, query, (row) => `${row.name} ${row.domain_force ?? ""}`);

  return (
    <div className="grid gap-3" data-testid="access-rules-list">
      <div className="ax-list-head">
        <h2 className="ax-list-title"><Term tech="ir.rule">Record rules</Term></h2>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={onCreate}
          data-testid="access-new-rule"
        >
          New rule
        </Button>
      </div>
      {rows.length > 0 || query ? (
        <input
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Filter by name or domain"
          aria-label="Filter record rules"
          data-testid="access-rules-filter"
          className="ax-search"
        />
      ) : null}
      {loading ? (
        <div className="grid gap-2" data-testid="access-rules-loading">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : filtered.length === 0 ? (
        <AccessStateGuide
          testId="access-rules-empty"
          guide={
            rows.length === 0
              ? accessEmptyGuide("rules", model?.trim() || "this model")
              : {
                  title: `No rule matches “${query}”`,
                  why: "The filter checks rule names and domains only.",
                  next: "Clear the filter, or create a new rule.",
                }
          }
          actions={
            <Button type="button" variant="secondary" size="sm" onClick={onCreate}>
              Create rule
            </Button>
          }
        />
      ) : (
        <ul className="ax-list">
          {filtered.map((row) => {
            const selected = selectedId === row.id;
            const global = row.global || (row.group_ids ?? []).length === 0;
            return (
              <li key={row.id}>
                <div
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
                  className="ax-list-row"
                >
                  <div className="min-w-0">
                    <p className="ax-list-name">
                      {row.name}
                      {global ? (
                        <span className="ax-tag" style={{ marginLeft: 6 }}>
                          Global
                        </span>
                      ) : null}
                    </p>
                    <p className="ax-list-meta is-mono">{row.domain_force || "[]"}</p>
                  </div>
                  <AccessCrudLetters value={row} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
