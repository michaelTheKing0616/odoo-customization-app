"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { IconFields } from "@/components/ui/icons";
import { fieldTypeLabel, filterByQuery, isCustomTechnicalName } from "@/lib/builderForm";
import type { FieldRow } from "@/lib/api";
import { cn } from "@/lib/cn";

type FieldListProps = {
  fields: FieldRow[];
  loading?: boolean;
  selectedFieldId: number | null;
  query: string;
  onQueryChange: (query: string) => void;
  onSelect: (row: FieldRow) => void;
  onCreate: () => void;
  onRemoveFromModel: (row: FieldRow) => void;
  designerHref: string;
};

export function FieldList({
  fields,
  loading,
  selectedFieldId,
  query,
  onQueryChange,
  onSelect,
  onCreate,
  onRemoveFromModel,
  designerHref,
}: FieldListProps) {
  const filtered = filterByQuery(
    fields,
    query,
    (row) => `${row.name} ${row.field_description} ${row.ttype}`,
  );

  return (
    <div className="space-y-3" data-testid="builder-field-list">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">Fields</h3>
        <Button type="button" variant="secondary" size="sm" onClick={onCreate} data-testid="builder-new-field">
          New field
        </Button>
      </div>
      <input
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder="Filter by name, label, or type"
        aria-label="Filter fields"
        data-testid="builder-fields-filter"
        className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 text-sm text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
      />
      {loading ? (
        <div className="space-y-2" data-testid="builder-fields-loading">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={<IconFields className="h-5 w-5" />}
          title={fields.length === 0 ? "No x_ fields on this model" : "No matching fields"}
          description={
            fields.length === 0
              ? "Add a custom field, then optionally inject it into form, list, and search."
              : "Try a different filter."
          }
          action={
            <Button type="button" variant="primary" size="sm" onClick={onCreate}>
              Add field
            </Button>
          }
        />
      ) : (
        <ul className="space-y-2">
          {filtered.map((row) => {
            const selected = selectedFieldId === row.id;
            const custom = isCustomTechnicalName(row.name);
            return (
              <li key={row.id}>
                <Card
                  className={cn(
                    "p-3 transition-colors",
                    selected && "border-accent bg-accent-subtle",
                  )}
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <button
                      type="button"
                      className="min-w-0 text-left"
                      onClick={() => onSelect(row)}
                      data-testid={`builder-field-row-${row.name}`}
                    >
                      <p className="truncate text-sm font-medium text-ink">
                        {row.field_description || row.name}
                      </p>
                      <p className="mt-0.5 truncate font-mono text-[11px] text-muted">{row.name}</p>
                    </button>
                    <div className="flex flex-wrap items-center gap-1">
                      <Badge variant="default">{fieldTypeLabel(row.ttype)}</Badge>
                      {row.required ? <Badge variant="warning">Required</Badge> : null}
                      {row.readonly ? <Badge variant="info">Readonly</Badge> : null}
                    </div>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {custom ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => onSelect(row)}
                      >
                        Edit properties
                      </Button>
                    ) : null}
                    <Button type="button" variant="ghost" size="sm" asChild>
                      <Link href={designerHref}>Hide in View Designer</Link>
                    </Button>
                    {custom ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="text-danger"
                        onClick={() => onRemoveFromModel(row)}
                        data-testid={`builder-remove-field-${row.name}`}
                      >
                        Remove from model
                      </Button>
                    ) : null}
                  </div>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
      <p className="text-xs text-muted">
        Hide in View Designer removes the widget from a layout. Remove from model deprecates or
        drops the column.
      </p>
    </div>
  );
}
