"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/cn";
import { Skeleton } from "@/components/ui/layout-primitives";

export type DataTableColumn<T> = {
  id: string;
  header: string;
  accessor: (row: T) => React.ReactNode;
  sortValue?: (row: T) => string | number;
  className?: string;
};

type DataTableProps<T> = {
  columns: DataTableColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  loading?: boolean;
  selectable?: boolean;
  selectedKeys?: Set<string>;
  onSelectedKeysChange?: (keys: Set<string>) => void;
  bulkActions?: React.ReactNode;
  emptyState?: React.ReactNode;
  virtualizeThreshold?: number;
  rowHeight?: number;
  density?: "comfortable" | "compact";
  onDensityChange?: (density: "comfortable" | "compact") => void;
};

const ROW_HEIGHT = { comfortable: 40, compact: 32 } as const;

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading,
  selectable,
  selectedKeys,
  onSelectedKeysChange,
  bulkActions,
  emptyState,
  virtualizeThreshold = 200,
  rowHeight,
  density = "comfortable",
  onDensityChange,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<{ id: string; dir: "asc" | "desc" } | null>(null);
  const [scrollTop, setScrollTop] = useState(0);

  const sortedRows = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.id === sort.id);
    if (!col?.sortValue) return rows;
    const copy = [...rows];
    copy.sort((a, b) => {
      const av = col.sortValue!(a);
      const bv = col.sortValue!(b);
      if (av < bv) return sort.dir === "asc" ? -1 : 1;
      if (av > bv) return sort.dir === "asc" ? 1 : -1;
      return 0;
    });
    return copy;
  }, [columns, rows, sort]);

  const rh = rowHeight ?? ROW_HEIGHT[density];
  const useVirtual = sortedRows.length >= virtualizeThreshold;
  const viewportHeight = 360;
  const start = useVirtual ? Math.floor(scrollTop / rh) : 0;
  const visibleCount = useVirtual ? Math.ceil(viewportHeight / rh) + 4 : sortedRows.length;
  const visibleRows = useVirtual
    ? sortedRows.slice(start, start + visibleCount)
    : sortedRows;
  const padTop = useVirtual ? start * rh : 0;
  const padBottom = useVirtual
    ? Math.max(0, (sortedRows.length - start - visibleRows.length) * rh)
    : 0;

  const allSelected =
    selectable &&
    selectedKeys &&
    rows.length > 0 &&
    rows.every((r) => selectedKeys.has(rowKey(r)));

  function toggleAll() {
    if (!onSelectedKeysChange) return;
    if (allSelected) {
      onSelectedKeysChange(new Set());
    } else {
      onSelectedKeysChange(new Set(rows.map(rowKey)));
    }
  }

  function toggleRow(key: string) {
    if (!onSelectedKeysChange || !selectedKeys) return;
    const next = new Set(selectedKeys);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    onSelectedKeysChange(next);
  }

  return (
    <div className="space-y-2" data-testid="data-table">
      <div className="flex items-center justify-between gap-2">
        {selectable && selectedKeys && selectedKeys.size > 0 ? (
          <div className="flex items-center gap-2 text-sm text-muted">
            <span>{selectedKeys.size} selected</span>
            {bulkActions}
          </div>
        ) : (
          <span />
        )}
        {onDensityChange ? (
          <button
            type="button"
            className="text-xs text-accent hover:underline"
            onClick={() =>
              onDensityChange(density === "comfortable" ? "compact" : "comfortable")
            }
          >
            Density: {density}
          </button>
        ) : null}
      </div>
      <div className="overflow-auto rounded-md border border-border-subtle">
        <table className="min-w-full text-sm">
          <thead className="sticky top-0 z-10 bg-surface-muted">
            <tr>
              {selectable ? (
                <th className="w-10 px-2 py-2">
                  <input
                    type="checkbox"
                    aria-label="Select all rows"
                    checked={!!allSelected}
                    onChange={toggleAll}
                  />
                </th>
              ) : null}
              {columns.map((col) => (
                <th
                  key={col.id}
                  className={cn("px-3 py-2 text-left font-medium text-ink", col.className)}
                >
                  {col.sortValue ? (
                    <button
                      type="button"
                      className="inline-flex items-center gap-1 hover:text-accent"
                      onClick={() =>
                        setSort((prev) =>
                          prev?.id === col.id
                            ? { id: col.id, dir: prev.dir === "asc" ? "desc" : "asc" }
                            : { id: col.id, dir: "asc" },
                        )
                      }
                    >
                      {col.header}
                      {sort?.id === col.id ? (sort.dir === "asc" ? " ↑" : " ↓") : null}
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody
            onScroll={
              useVirtual
                ? (e) => setScrollTop((e.target as HTMLDivElement).scrollTop)
                : undefined
            }
            style={useVirtual ? { display: "block", maxHeight: viewportHeight, overflow: "auto" } : undefined}
          >
            {loading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <tr key={`sk-${i}`}>
                    <td colSpan={columns.length + (selectable ? 1 : 0)} className="px-3 py-2">
                      <Skeleton className="h-6 w-full" />
                    </td>
                  </tr>
                ))
              : null}
            {!loading && sortedRows.length === 0 ? (
              <tr>
                <td colSpan={columns.length + (selectable ? 1 : 0)} className="px-3 py-8">
                  {emptyState ?? <p className="text-center text-muted">No rows</p>}
                </td>
              </tr>
            ) : null}
            {!loading && padTop > 0 ? (
              <tr aria-hidden style={{ height: padTop }}>
                <td colSpan={columns.length + (selectable ? 1 : 0)} />
              </tr>
            ) : null}
            {!loading &&
              visibleRows.map((row) => {
                const key = rowKey(row);
                return (
                  <tr key={key} className="border-t border-border-subtle hover:bg-surface-muted">
                    {selectable ? (
                      <td className="w-10 px-2 py-2">
                        <input
                          type="checkbox"
                          aria-label={`Select row ${key}`}
                          checked={selectedKeys?.has(key) ?? false}
                          onChange={() => toggleRow(key)}
                        />
                      </td>
                    ) : null}
                    {columns.map((col) => (
                      <td key={col.id} className={cn("px-3 py-2", col.className)}>
                        {col.accessor(row)}
                      </td>
                    ))}
                  </tr>
                );
              })}
            {!loading && padBottom > 0 ? (
              <tr aria-hidden style={{ height: padBottom }}>
                <td colSpan={columns.length + (selectable ? 1 : 0)} />
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
