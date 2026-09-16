"use client";

import { useState, type ReactNode } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { ChevronRight, IconMenus } from "@/components/ui/icons";
import { EMPTY_STATES } from "@/lib/copy-guide";
import {
  childrenOf,
  rootMenus,
  visibleMenuIds,
} from "@/lib/menuForm";
import type { MenuNode } from "@/lib/api";
import { cn } from "@/lib/cn";

type MenusTreeProps = {
  menus: MenuNode[];
  loading?: boolean;
  selectedId: number | null;
  query: string;
  onQueryChange: (query: string) => void;
  onSelect: (menu: MenuNode) => void;
  onCreate: () => void;
};

export function MenusTree({
  menus,
  loading,
  selectedId,
  query,
  onQueryChange,
  onSelect,
  onCreate,
}: MenusTreeProps) {
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set());
  const visible = visibleMenuIds(menus, query);
  const roots = rootMenus(menus).filter((m) => visible == null || visible.has(m.id));

  function toggle(id: number) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function renderNodes(nodes: MenuNode[]): ReactNode {
    return nodes.map((menu) => {
      const kids = childrenOf(menus, menu.id).filter(
        (c) => visible == null || visible.has(c.id),
      );
      const open = !collapsed.has(menu.id);
      const selected = selectedId === menu.id;
      return (
        <li key={menu.id}>
          <div className="flex items-stretch gap-0.5">
            {kids.length > 0 ? (
              <button
                type="button"
                aria-label={open ? `Collapse ${menu.name}` : `Expand ${menu.name}`}
                onClick={() => toggle(menu.id)}
                className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-muted hover:bg-surface-muted hover:text-ink"
              >
                <ChevronRight
                  className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-90")}
                />
              </button>
            ) : (
              <span className="mt-1 w-7 shrink-0" />
            )}
            <Card
              role="button"
              tabIndex={0}
              aria-pressed={selected}
              data-testid={`menu-row-${menu.id}`}
              onClick={() => onSelect(menu)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect(menu);
                }
              }}
              className={cn(
                "min-w-0 flex-1 cursor-pointer p-2.5 transition-colors hover:bg-surface-muted",
                selected && "border-accent bg-accent-subtle",
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">{menu.name}</p>
                  <p className="mt-0.5 font-mono text-[11px] text-muted">
                    #{menu.id} · seq {menu.sequence}
                  </p>
                </div>
                {menu.action_id ? (
                  <Badge variant="info">Action {menu.action_id}</Badge>
                ) : (
                  <Badge variant="default">No action</Badge>
                )}
              </div>
            </Card>
          </div>
          {open && kids.length > 0 ? (
            <ul className="ml-4 mt-1 space-y-1 border-l border-border-subtle pl-2">
              {renderNodes(kids)}
            </ul>
          ) : null}
        </li>
      );
    });
  }

  return (
    <div className="space-y-3" data-testid="menus-tree">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-ui-title font-semibold text-ink">Menu tree</h2>
        <Button type="button" variant="secondary" size="sm" onClick={onCreate} data-testid="menus-new">
          New menu
        </Button>
      </div>
      <input
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder="Filter by name or id"
        aria-label="Filter menus"
        data-testid="menus-tree-filter"
        className="h-row w-full rounded-md border border-border-subtle bg-surface px-3 text-ui-body text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
      />
      {loading ? (
        <div className="space-y-2" data-testid="menus-tree-loading">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : roots.length === 0 ? (
        <EmptyState
          icon={<IconMenus className="h-5 w-5" />}
          title={menus.length === 0 ? "No menus yet" : "No matching menus"}
          description={
            menus.length === 0
              ? EMPTY_STATES.menus
              : "Try a different filter, or create a new menu."
          }
          action={
            <Button type="button" variant="primary" size="sm" onClick={onCreate}>
              Create menu
            </Button>
          }
        />
      ) : (
        <ul className="max-h-[32rem] space-y-1 overflow-auto pr-1">{renderNodes(roots)}</ul>
      )}
    </div>
  );
}
