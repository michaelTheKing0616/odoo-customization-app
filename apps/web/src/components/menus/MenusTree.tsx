"use client";

import { useEffect, useMemo, useRef, useState, type DragEvent, type KeyboardEvent } from "react";
import { Button } from "@/components/ui/Button";
import { EmptyState, Skeleton } from "@/components/ui/layout-primitives";
import { ChevronRight, CircleAlert, IconDragHandle, IconMenus, X } from "@/components/ui/icons";
import { visibleMenuIds } from "@/lib/menuForm";
import {
  dropHint,
  dropVerdict,
  flattenMenuTree,
  treeKeyAction,
  typeaheadMatch,
  type DropVerdict,
  type TreeRow,
} from "@/lib/menuTree";
import type { MenuNode, WindowActionRow } from "@/lib/api";

export type DropRefusal = Extract<DropVerdict, { ok: false }>;

type MenusTreeProps = {
  menus: MenuNode[];
  actions?: WindowActionRow[];
  loading?: boolean;
  selectedId: number | null;
  query: string;
  onQueryChange: (query: string) => void;
  onSelect: (menu: MenuNode) => void;
  onCreate: () => void;
  /** Drag a row onto a new parent. The move is staged; the detail panel saves it. */
  onMove?: (menu: MenuNode, parentId: number | null) => void;
  canMove?: boolean;
  moveBlockedReason?: string | null;
  /** Row whose parent change is staged but not saved yet. */
  stagedMenuId?: number | null;
  /** Start with a refusal on screen (harness and tests). */
  defaultRefusal?: DropRefusal | null;
  /** Menus failed to load: say so instead of claiming the database has none. */
  unavailable?: boolean;
};

type Over = { id: number | "root"; verdict: DropVerdict };

const TYPEAHEAD_RESET_MS = 600;

export function MenusTree({
  menus,
  actions = [],
  loading,
  selectedId,
  query,
  onQueryChange,
  onSelect,
  onCreate,
  onMove,
  canMove = true,
  moveBlockedReason,
  stagedMenuId = null,
  defaultRefusal = null,
  unavailable = false,
}: MenusTreeProps) {
  const [collapsed, setCollapsed] = useState<Set<number>>(() => new Set());
  const [focusId, setFocusId] = useState<number | null>(selectedId);
  const [dragId, setDragId] = useState<number | null>(null);
  const [over, setOver] = useState<Over | null>(null);
  const [refusal, setRefusal] = useState<DropRefusal | null>(defaultRefusal);
  const [announce, setAnnounce] = useState("");
  const rowRefs = useRef(new Map<number, HTMLLIElement>());
  const overRef = useRef<Over | null>(null);
  const finishedRef = useRef(false);
  const typeahead = useRef<{ text: string; at: number }>({ text: "", at: 0 });

  const visible = useMemo(() => visibleMenuIds(menus, query), [menus, query]);
  const rows = useMemo(() => flattenMenuTree(menus, { collapsed, visible }), [menus, collapsed, visible]);
  const actionById = useMemo(() => new Map(actions.map((a) => [a.id, a])), [actions]);
  const movable = Boolean(onMove) && canMove;

  const rowIds = rows.map((r) => r.menu.id);
  const tabStop =
    focusId != null && rowIds.includes(focusId)
      ? focusId
      : selectedId != null && rowIds.includes(selectedId)
        ? selectedId
        : (rowIds[0] ?? null);

  useEffect(() => {
    if (selectedId != null) setFocusId(selectedId);
  }, [selectedId]);

  function focusRow(id: number) {
    setFocusId(id);
    const el = rowRefs.current.get(id);
    if (el) {
      el.focus({ preventScroll: true });
      el.scrollIntoView?.({ block: "nearest" });
    }
  }

  function setExpanded(id: number, open: boolean) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (open) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectRow(row: TreeRow) {
    setFocusId(row.menu.id);
    onSelect(row.menu);
  }

  function onTreeKeyDown(e: KeyboardEvent<HTMLUListElement>) {
    if (e.altKey || e.ctrlKey || e.metaKey) return;
    const action = treeKeyAction(rows, tabStop, e.key);
    if (action) {
      e.preventDefault();
      if (action.type === "focus") focusRow(action.id);
      else if (action.type === "expand") setExpanded(action.id, true);
      else if (action.type === "collapse") setExpanded(action.id, false);
      else {
        const row = rows.find((r) => r.menu.id === action.id);
        if (row) selectRow(row);
      }
      return;
    }
    if (e.key.length === 1 && /\S/.test(e.key)) {
      const now = Date.now();
      const buf = now - typeahead.current.at > TYPEAHEAD_RESET_MS ? e.key : typeahead.current.text + e.key;
      typeahead.current = { text: buf, at: now };
      // A longer prefix keeps matching the current row; a fresh letter moves on.
      const idx = rowIds.indexOf(tabStop ?? -1);
      const from = buf.length > 1 && idx >= 0 ? rowIds[(idx - 1 + rowIds.length) % rowIds.length] : tabStop;
      const hit = typeaheadMatch(rows, from, buf);
      if (hit != null) {
        e.preventDefault();
        focusRow(hit);
      }
    }
  }

  /* ---------- drag to re-parent (pointer); Parent field is the keyboard path ---------- */

  function setOverIfChanged(next: Over | null) {
    const prev = overRef.current;
    if (prev?.id === next?.id && prev?.verdict.ok === next?.verdict.ok) return;
    overRef.current = next;
    setOver(next);
  }

  function startDrag(e: DragEvent<HTMLLIElement>, row: TreeRow) {
    if (!movable) {
      e.preventDefault();
      return;
    }
    finishedRef.current = false;
    setDragId(row.menu.id);
    setRefusal(null);
    e.dataTransfer.effectAllowed = "move";
    try {
      e.dataTransfer.setData("text/plain", String(row.menu.id));
    } catch {
      /* some synthetic DataTransfers are read-only */
    }
    setAnnounce(`Moving “${row.menu.name}”. Drop it on a new parent, or on Top level.`);
  }

  function overTarget(e: DragEvent<HTMLElement>, target: number | null) {
    if (dragId == null) return;
    const verdict = dropVerdict(menus, dragId, target);
    e.preventDefault();
    e.dataTransfer.dropEffect = verdict.ok ? "move" : "none";
    setOverIfChanged({ id: target ?? "root", verdict });
  }

  function finish(target: number | null) {
    if (dragId == null || finishedRef.current) return;
    finishedRef.current = true;
    const dragged = menus.find((m) => m.id === dragId);
    const verdict = dropVerdict(menus, dragId, target);
    if (verdict.ok && dragged) {
      onMove?.(dragged, verdict.parentId);
      setAnnounce(`${verdict.title}. Not saved yet. Save the menu to write it to Odoo.`);
    } else if (!verdict.ok && verdict.kind !== "same") {
      setRefusal(verdict);
      setAnnounce(`${verdict.title}. ${verdict.why}`);
    } else if (!verdict.ok) {
      setAnnounce(verdict.title);
    }
  }

  function dropOn(e: DragEvent<HTMLElement>, target: number | null) {
    e.preventDefault();
    finish(target);
    endDrag();
  }

  function endDrag() {
    // A refused target sets dropEffect "none", so the browser never fires drop. Refuse it here.
    const last = overRef.current;
    if (last && !finishedRef.current) finish(last.id === "root" ? null : last.id);
    overRef.current = null;
    setOver(null);
    setDragId(null);
  }

  function dropState(id: number | "root"): "ok" | "refused" | "same" | undefined {
    if (dragId == null || over?.id !== id) return undefined;
    if (over.verdict.ok) return "ok";
    return over.verdict.kind === "same" ? "same" : "refused";
  }

  const total = menus.length;

  return (
    <div className="mn-tree" data-testid="menus-tree">
      <div className="mn-tree-head">
        <h2 className="mn-tree-title" id="menus-tree-title">
          Menu tree
          {total > 0 && !loading ? <span className="mn-count">{total}</span> : null}
        </h2>
        <Button type="button" variant="secondary" size="sm" onClick={onCreate} data-testid="menus-new">
          New menu
        </Button>
      </div>
      <input
        type="search"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        placeholder="Filter by name or id…"
        aria-label="Filter menus"
        data-testid="menus-tree-filter"
        className="mn-search"
        autoComplete="off"
        spellCheck={false}
      />
      {rows.length > 0 && !loading ? (
        <ul className="mn-legend" aria-label="Tree keys" data-testid="menus-tree-legend">
          <li className="mn-legend-key">
            <kbd>↑</kbd>
            <kbd>↓</kbd> move
          </li>
          <li className="mn-legend-key">
            <kbd>→</kbd>
            <kbd>←</kbd> open or close
          </li>
          <li className="mn-legend-key">
            <kbd>Enter</kbd> edit
          </li>
          <li>{movable ? "Drag or change Parent to re-parent" : "Change Parent to re-parent"}</li>
        </ul>
      ) : null}

      {refusal ? (
        <div className="mn-guide" data-tone="danger" data-testid="menus-drop-refusal">
          <div className="mn-guide-head">
            <CircleAlert className="mn-guide-icon" aria-hidden />
            <p className="mn-guide-title" data-testid="menus-drop-refusal-title">
              {refusal.title}
            </p>
            <button
              type="button"
              className="mn-guide-close"
              aria-label="Dismiss"
              onClick={() => setRefusal(null)}
            >
              <X aria-hidden />
            </button>
          </div>
          <dl className="mn-guide-rows">
            <dt>Why</dt>
            <dd data-testid="menus-drop-refusal-why">{refusal.why}</dd>
            <dt>Next</dt>
            <dd>{refusal.next}</dd>
          </dl>
        </div>
      ) : null}

      {!movable && onMove && moveBlockedReason && rows.length > 0 ? (
        <p className="mn-quiet" data-testid="menus-move-blocked">
          Dragging is off: {moveBlockedReason}
        </p>
      ) : null}

      {loading ? (
        <div className="mn-list-box" role="status" data-testid="menus-tree-loading" aria-busy="true" aria-label="Loading menus">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="mn-skeleton-row" style={{ paddingLeft: 12 + (i % 3) * 20 }}>
              <Skeleton className="h-4 w-4" />
              <Skeleton className="h-3.5 w-3/5" />
              <Skeleton className="h-5 w-full" />
            </div>
          ))}
        </div>
      ) : unavailable && total === 0 ? (
        <p className="mn-quiet" data-testid="menus-tree-unavailable">
          The tree appears once Odoo returns the menus. Use Try again above.
        </p>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<IconMenus className="h-5 w-5" />}
          title={total === 0 ? "No menus yet" : "No matching menus"}
          description={
            total === 0
              ? "Create a root menu to add an app tile to Odoo's home screen."
              : "No label or id matches this filter. Clear it to see the whole tree."
          }
          action={
            total === 0 ? (
              <Button type="button" variant="secondary" size="sm" onClick={onCreate}>
                Create menu
              </Button>
            ) : (
              <Button type="button" variant="secondary" size="sm" onClick={() => onQueryChange("")}>
                Clear filter
              </Button>
            )
          }
        />
      ) : (
        <div
          className="mn-list-box"
          onDragLeave={(e) => {
            if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOverIfChanged(null);
          }}
        >
          <ul
            role="tree"
            aria-labelledby="menus-tree-title"
            className="mn-tree-list"
            onKeyDown={onTreeKeyDown}
            data-testid="menus-tree-list"
          >
            {rows.map((row) => {
              const { menu } = row;
              const selected = selectedId === menu.id;
              const bound = menu.action_id != null ? actionById.get(menu.action_id) : undefined;
              const drop = dropState(menu.id);
              const staged = stagedMenuId === menu.id;
              const metaId = `menu-row-meta-${menu.id}`;
              return (
                <li
                  key={menu.id}
                  ref={(el) => {
                    if (el) rowRefs.current.set(menu.id, el);
                    else rowRefs.current.delete(menu.id);
                  }}
                  role="treeitem"
                  aria-level={row.level}
                  aria-setsize={row.setsize}
                  aria-posinset={row.posinset}
                  aria-expanded={row.hasChildren ? row.expanded : undefined}
                  aria-selected={selected}
                  aria-label={menu.name}
                  aria-describedby={metaId}
                  tabIndex={tabStop === menu.id ? 0 : -1}
                  className="mn-row"
                  style={{ ["--mn-level" as string]: row.level }}
                  data-level={row.level}
                  data-testid={`menu-row-${menu.id}`}
                  data-draggable={movable ? "true" : "false"}
                  data-dragging={dragId === menu.id ? "true" : undefined}
                  data-drop={drop}
                  data-staged={staged ? "true" : undefined}
                  draggable={movable}
                  onClick={() => selectRow(row)}
                  onFocus={() => setFocusId(menu.id)}
                  onDragStart={(e) => startDrag(e, row)}
                  onDragEnter={(e) => overTarget(e, menu.id)}
                  onDragOver={(e) => overTarget(e, menu.id)}
                  onDrop={(e) => dropOn(e, menu.id)}
                  onDragEnd={endDrag}
                >
                  <span
                    className="mn-chev"
                    data-has-children={row.hasChildren ? "true" : "false"}
                    aria-hidden
                    data-testid={row.hasChildren ? `menu-row-toggle-${menu.id}` : undefined}
                    onClick={(e) => {
                      if (!row.hasChildren) return;
                      e.stopPropagation();
                      setExpanded(menu.id, !row.expanded);
                      setFocusId(menu.id);
                    }}
                  >
                    {row.hasChildren ? <ChevronRight /> : null}
                  </span>
                  <span className="mn-grip" aria-hidden>
                    <IconDragHandle />
                  </span>
                  <span className="mn-row-main">
                    <span className="mn-row-name" style={{ display: "block" }}>
                      {menu.name}
                    </span>
                    <span className="mn-row-meta" id={metaId} style={{ display: "block" }}>
                      {drop ? (
                        <span className="mn-drop-reason" data-testid="menus-drop-hint">
                          {over ? dropHint(over.verdict) : null}
                        </span>
                      ) : (
                        <>
                          #{menu.id}, sequence {menu.sequence}
                          {menu.group_ids && menu.group_ids.length > 0
                            ? `, ${menu.group_ids.length === 1 ? "1 group" : `${menu.group_ids.length} groups`}`
                            : ""}
                        </>
                      )}
                    </span>
                  </span>
                  <span className="mn-row-chips">
                    {staged ? (
                      <span className="mn-chip" data-tone="warn" data-testid="menus-row-staged">
                        Unsaved move
                      </span>
                    ) : bound?.res_model ? (
                      <span className="mn-chip" title={`Opens ${bound.res_model} (action #${bound.id})`}>
                        {bound.res_model}
                      </span>
                    ) : menu.action_id ? (
                      <span className="mn-chip">Action {menu.action_id}</span>
                    ) : row.hasChildren ? null : (
                      <span className="mn-chip" data-tone="muted">
                        No action
                      </span>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
          {dragId != null ? (
            <div
              className="mn-rootzone"
              data-testid="menus-drop-root"
              data-drop={dropState("root")}
              aria-hidden
              onDragEnter={(e) => overTarget(e, null)}
              onDragOver={(e) => overTarget(e, null)}
              onDrop={(e) => dropOn(e, null)}
            >
              {over?.id === "root" ? dropHint(over.verdict) : "Top level: drop here to make it an app tile"}
            </div>
          ) : null}
        </div>
      )}
      <p className="sr-only-live" role="status" aria-live="polite" data-testid="menus-tree-live">
        {announce}
      </p>
    </div>
  );
}
