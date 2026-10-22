"use client";

import { Button } from "@/components/ui/Button";
import { Skeleton } from "@/components/ui/layout-primitives";
import { AccessCrudLetters } from "@/components/access/AccessCrudLetters";
import { AccessStateGuide } from "@/components/access/AccessStateGuide";
import { filterByQuery } from "@/lib/accessForm";
import { accessEmptyGuide } from "@/lib/accessScreen";
import type { AccessRightRow } from "@/lib/api";

type AccessRightsListProps = {
  rows: AccessRightRow[];
  loading?: boolean;
  selectedId: number | null;
  query: string;
  onQueryChange: (query: string) => void;
  onSelect: (row: AccessRightRow) => void;
  onCreate: () => void;
  /** Model name for the empty-state copy. */
  model?: string;
  /** Section title, e.g. "ir.access rows" on Odoo 20. */
  title?: string;
};

export function AccessRightsList({
  rows,
  loading,
  selectedId,
  query,
  onQueryChange,
  onSelect,
  onCreate,
  model,
  title = "Access lines",
}: AccessRightsListProps) {
  const filtered = filterByQuery(rows, query, (row) => `${row.name} ${row.group_name ?? ""}`);

  return (
    <div className="grid gap-3" data-testid="access-rights-list">
      <div className="ax-list-head">
        <h2 className="ax-list-title">{title}</h2>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          onClick={onCreate}
          data-testid="access-new-right"
        >
          New line
        </Button>
      </div>
      {rows.length > 0 || query ? (
        <input
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          placeholder="Filter by name or group"
          aria-label="Filter access rights"
          data-testid="access-rights-filter"
          className="ax-search"
        />
      ) : null}
      {loading ? (
        <div className="grid gap-2" data-testid="access-rights-loading">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : filtered.length === 0 ? (
        <AccessStateGuide
          testId="access-rights-empty"
          guide={
            rows.length === 0
              ? accessEmptyGuide("lines", model?.trim() || "this model")
              : {
                  title: `No access line matches “${query}”`,
                  why: "The filter checks line names and group names only.",
                  next: "Clear the filter, or create a new line.",
                }
          }
          actions={
            <Button type="button" variant="secondary" size="sm" onClick={onCreate}>
              Create access
            </Button>
          }
        />
      ) : (
        <ul className="ax-list">
          {filtered.map((row) => {
            const selected = selectedId === row.id;
            const global = row.group_id == null;
            return (
              <li key={row.id}>
                <div
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
                  className="ax-list-row"
                >
                  <div className="min-w-0">
                    <p className="ax-list-name">{row.name}</p>
                    <p className="ax-list-meta">
                      {global ? (
                        <span className="ax-tag" style={{ marginRight: 6 }}>
                          Global
                        </span>
                      ) : null}
                      {row.group_name ?? "All users"}
                    </p>
                  </div>
                  <AccessCrudLetters value={row} testId={`access-right-crud-${row.id}`} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
