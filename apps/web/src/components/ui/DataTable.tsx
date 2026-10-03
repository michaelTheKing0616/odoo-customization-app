"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
} from "react";
import {
  TableVirtuoso,
  type TableComponents,
  type TableVirtuosoHandle,
} from "react-virtuoso";
import { cn } from "@/lib/cn";
import { Skeleton } from "@/components/ui/layout-primitives";

export const DEFAULT_VIRTUALIZE_THRESHOLD = 50;
const VIEWPORT_HEIGHT = 360;

export type DataTableColumn<T> = {
  id: string;
  header: string;
  accessor: (row: T) => React.ReactNode;
  sortValue?: (row: T) => string | number;
  className?: string;
};

export type DataTableSortState = { id: string; dir: "asc" | "desc" } | null;

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

type DataTableVirtuosoContext<T> = {
  colCount: number;
  activeKey: string | null;
  getRowKey: (row: T) => string;
  onActivateIndex: (index: number) => void;
};

export function sortDataTableRows<T>(
  rows: readonly T[],
  columns: readonly DataTableColumn<T>[],
  sort: DataTableSortState,
): T[] {
  if (!sort) return [...rows];
  const col = columns.find((c) => c.id === sort.id);
  if (!col?.sortValue) return [...rows];
  const copy = [...rows];
  copy.sort((a, b) => {
    const av = col.sortValue!(a);
    const bv = col.sortValue!(b);
    if (av < bv) return sort.dir === "asc" ? -1 : 1;
    if (av > bv) return sort.dir === "asc" ? 1 : -1;
    return 0;
  });
  return copy;
}

export function shouldVirtualizeRows(
  rowCount: number,
  threshold: number = DEFAULT_VIRTUALIZE_THRESHOLD,
): boolean {
  return rowCount > threshold;
}

export function stepActiveRowIndex(
  current: number,
  key: "ArrowDown" | "ArrowUp",
  rowCount: number,
): number {
  if (rowCount <= 0) return 0;
  if (key === "ArrowDown") return Math.min(rowCount - 1, current + 1);
  return Math.max(0, current - 1);
}

function rowDomId(key: string): string {
  return `data-table-row-${key}`;
}

function stripBlockDisplay(style?: CSSProperties): CSSProperties | undefined {
  if (!style) return style;
  const next = { ...style };
  delete next.display;
  return next;
}

const virtuosoComponents: TableComponents<unknown, DataTableVirtuosoContext<unknown>> = {
  Table: ({ style, children }) => (
    <table className="min-w-full table-fixed text-sm" style={style}>
      {children}
    </table>
  ),
  TableHead: forwardRef(({ style, children }, ref) => (
    <thead ref={ref} className="sticky top-0 z-10 bg-surface-muted" style={style}>
      {children}
    </thead>
  )),
  TableBody: forwardRef(({ style, context: _context, ...props }, ref) => (
    <tbody {...props} ref={ref} style={stripBlockDisplay(style)} />
  )),
  FillerRow: ({ height, context }) => (
    <tr aria-hidden>
      <td colSpan={context.colCount} style={{ height, padding: 0, border: 0 }} />
    </tr>
  ),
  TableRow: ({ item, context, ...props }) => {
    const key = context.getRowKey(item);
    const active = context.activeKey === key;
    return (
      <tr
        {...props}
        id={rowDomId(key)}
        data-active={active ? "true" : undefined}
        aria-selected={active}
        className="border-t border-border-subtle hover:bg-surface-muted"
        onClick={() => context.onActivateIndex(props["data-item-index"])}
      />
    );
  },
};

function HeaderRow<T>({
  columns,
  selectable,
  allSelected,
  sort,
  onToggleAll,
  onSort,
}: {
  columns: DataTableColumn<T>[];
  selectable?: boolean;
  allSelected: boolean;
  sort: DataTableSortState;
  onToggleAll: () => void;
  onSort: (id: string) => void;
}) {
  return (
    <tr>
      {selectable ? (
        <th className="w-10 px-2 py-2">
          <input
            type="checkbox"
            aria-label="Select all rows"
            checked={allSelected}
            onChange={onToggleAll}
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
              onClick={() => onSort(col.id)}
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
  );
}

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
  virtualizeThreshold = DEFAULT_VIRTUALIZE_THRESHOLD,
  rowHeight,
  density = "comfortable",
  onDensityChange,
}: DataTableProps<T>) {
  const [sort, setSort] = useState<DataTableSortState>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const virtuosoRef = useRef<TableVirtuosoHandle>(null);

  const sortedRows = useMemo(
    () => sortDataTableRows(rows, columns, sort),
    [columns, rows, sort],
  );

  const rh = rowHeight ?? ROW_HEIGHT[density];
  const useVirtual = !loading && shouldVirtualizeRows(sortedRows.length, virtualizeThreshold);
  const colCount = columns.length + (selectable ? 1 : 0);
  const activeRow = sortedRows[activeIndex];
  const activeKey = activeRow ? rowKey(activeRow) : null;

  useEffect(() => {
    setActiveIndex((current) => {
      if (sortedRows.length === 0) return 0;
      return Math.min(current, sortedRows.length - 1);
    });
  }, [sortedRows.length]);

  useEffect(() => {
    if (!useVirtual || !virtuosoRef.current) return;
    virtuosoRef.current.scrollIntoView({ index: activeIndex, align: "center" });
  }, [activeIndex, useVirtual]);

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

  function cycleSort(id: string) {
    setSort((prev) =>
      prev?.id === id
        ? { id, dir: prev.dir === "asc" ? "desc" : "asc" }
        : { id, dir: "asc" },
    );
  }

  const handleTableKeyDown = useCallback(
    (event: KeyboardEvent<HTMLElement>) => {
      const key = event.key;
      if (key !== "ArrowDown" && key !== "ArrowUp") return;
      if (sortedRows.length === 0) return;
      event.preventDefault();
      setActiveIndex((current) => stepActiveRowIndex(current, key, sortedRows.length));
    },
    [sortedRows.length],
  );

  const virtuosoContext = useMemo<DataTableVirtuosoContext<T>>(
    () => ({
      colCount,
      activeKey,
      getRowKey: rowKey,
      onActivateIndex: setActiveIndex,
    }),
    [activeKey, colCount, rowKey],
  );

  const header = (
    <HeaderRow
      columns={columns}
      selectable={selectable}
      allSelected={!!allSelected}
      sort={sort}
      onToggleAll={toggleAll}
      onSort={cycleSort}
    />
  );

  function renderCells(row: T) {
    const key = rowKey(row);
    return (
      <>
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
      </>
    );
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
      {useVirtual ? (
        <TableVirtuoso
          ref={virtuosoRef}
          data={sortedRows}
          context={virtuosoContext as DataTableVirtuosoContext<unknown>}
          components={virtuosoComponents as TableComponents<T, DataTableVirtuosoContext<T>>}
          computeItemKey={(_index, row) => rowKey(row)}
          fixedHeaderContent={() => header}
          itemContent={(_index, row) => renderCells(row)}
          style={{ height: VIEWPORT_HEIGHT }}
          className="overflow-auto rounded-md border border-border-subtle"
          data-testid="data-table-scroll"
          tabIndex={0}
          role="grid"
          aria-rowcount={sortedRows.length}
          aria-activedescendant={activeKey ? rowDomId(activeKey) : undefined}
          onKeyDown={handleTableKeyDown}
          fixedItemHeight={rh}
          defaultItemHeight={rh}
          initialItemCount={Math.min(
            sortedRows.length,
            Math.ceil(VIEWPORT_HEIGHT / rh) + 4,
          )}
        />
      ) : (
        <div
          className="overflow-auto rounded-md border border-border-subtle"
          tabIndex={0}
          role="grid"
          aria-rowcount={sortedRows.length}
          aria-activedescendant={activeKey ? rowDomId(activeKey) : undefined}
          onKeyDown={handleTableKeyDown}
        >
          <table className="min-w-full table-fixed text-sm">
            <thead className="sticky top-0 z-10 bg-surface-muted">{header}</thead>
            <tbody>
              {loading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={`sk-${i}`}>
                      <td colSpan={colCount} className="px-3 py-2">
                        <Skeleton className="h-6 w-full" />
                      </td>
                    </tr>
                  ))
                : null}
              {!loading && sortedRows.length === 0 ? (
                <tr>
                  <td colSpan={colCount} className="px-3 py-8">
                    {emptyState ?? <p className="text-center text-muted">No rows</p>}
                  </td>
                </tr>
              ) : null}
              {!loading &&
                sortedRows.map((row, index) => {
                  const key = rowKey(row);
                  const active = key === activeKey;
                  return (
                    <tr
                      key={key}
                      id={rowDomId(key)}
                      data-active={active ? "true" : undefined}
                      aria-selected={active}
                      className="border-t border-border-subtle hover:bg-surface-muted"
                      onClick={() => setActiveIndex(index)}
                    >
                      {renderCells(row)}
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
