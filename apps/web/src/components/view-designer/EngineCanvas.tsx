"use client";

import { useEffect, useState, type DragEvent, type ReactNode } from "react";
import { Tooltip } from "@/components/ui/Tooltip";
import type { EngineNode, EngineRecord, Marker, Visibility } from "@/lib/api/view-engine";
import { MARKER_WORDS, whyHidden } from "@/lib/viewDesigner2a";
import {
  canDrop,
  dropLabel,
  fieldCount,
  visibilityChips,
  type DropPosition,
  type TreeIndex,
} from "@/lib/viewEngineOps";
import { Note } from "../view-designer/Note";
import styles from "./ViewDesigner.module.css";

export const FIELD_DRAG_TYPE = "application/x-ingenium-field";
const NODE_DRAG_TYPE = "application/x-ingenium-node";

type DropState = { target: string; position: DropPosition; ok: boolean; label: string } | null;

type EngineCanvasProps = {
  tree: EngineNode;
  index: TreeIndex;
  record: EngineRecord | null;
  selectedId: string | null;
  onSelect: (id: string, additive?: boolean) => void;
  onMove: (node: string, target: string, position: DropPosition) => void;
  onInsertField: (field: string, target: string, position: DropPosition) => void;
  /** Stage 2a overlays (all optional). */
  multiSelected?: string[];
  markers?: Record<string, Marker>;
  preview?: Visibility | null;
  commentCounts?: Record<string, number> | null;
  onOpenComments?: (id: string) => void;
  readOnly?: boolean;
  /** Stage 2c overlays (all optional). */
  heat?: Record<string, { level: number; label: string }> | null;
  cursors?: Record<string, string[]> | null;
  tourFocus?: string | null;
};

function isHidden(node: EngineNode): boolean {
  const v = node.attrs.invisible ?? node.attrs.column_invisible;
  return v === "1" || v === "True";
}

function valueText(record: EngineRecord | null, node: EngineNode): string {
  if (!record || !node.name) return "";
  const v = record[node.name];
  if (v === true) return "Yes";
  if (v === false || v === null || v === undefined) return "";
  return String(v);
}

/**
 * Edit render of a normalized Odoo screen. Odoo's own render (Open in Odoo) is
 * the reference; publish checks the result against what Odoo returns.
 */
export function EngineCanvas({
  tree,
  index,
  record,
  selectedId,
  onSelect,
  onMove,
  onInsertField,
  multiSelected,
  markers,
  preview,
  commentCounts,
  onOpenComments,
  readOnly = false,
  heat,
  cursors,
  tourFocus,
}: EngineCanvasProps) {
  const [drop, setDrop] = useState<DropState>(null);
  useEffect(() => {
    if (!tourFocus) return;
    document.querySelector(`[data-node-id="${CSS.escape(tourFocus)}"]`)?.scrollIntoView?.({ block: "center", behavior: "smooth" });
  }, [tourFocus]);
  const [tabs, setTabs] = useState<Record<string, string>>({});

  const positionFor = (e: DragEvent<HTMLElement>, node: EngineNode): DropPosition => {
    const rect = e.currentTarget.getBoundingClientRect();
    const y = (e.clientY - rect.top) / Math.max(rect.height, 1);
    const container = ["group", "page", "div", "sheet", "notebook"].includes(node.tag);
    if (container && y > 0.25 && y < 0.75) return "inside";
    return y < 0.5 ? "before" : "after";
  };

  const onDragOver = (e: DragEvent<HTMLElement>, node: EngineNode) => {
    const types = Array.from(e.dataTransfer.types);
    const adding = types.includes(FIELD_DRAG_TYPE);
    if (!adding && !types.includes(NODE_DRAG_TYPE)) return;
    e.preventDefault();
    e.stopPropagation();
    const position = positionFor(e, node);
    const draggingId = adding ? null : (window as unknown as { __ingDrag?: string }).__ingDrag ?? null;
    const dragTag = adding ? "field" : (draggingId ? index.byId.get(draggingId)?.tag : "field") ?? "field";
    const check = canDrop(index, dragTag, draggingId, node.id, position);
    e.dataTransfer.dropEffect = check.ok ? "move" : "none";
    setDrop({
      target: node.id,
      position,
      ok: check.ok,
      label: check.ok ? dropLabel(node, position, adding) : check.reason ?? "Not allowed here",
    });
  };

  const onDrop = (e: DragEvent<HTMLElement>, node: EngineNode) => {
    e.preventDefault();
    e.stopPropagation();
    const current = drop;
    setDrop(null);
    if (!current?.ok || current.target !== node.id) return;
    const field = e.dataTransfer.getData(FIELD_DRAG_TYPE);
    const moving = e.dataTransfer.getData(NODE_DRAG_TYPE);
    if (field) onInsertField(field, node.id, current.position);
    else if (moving) onMove(moving, node.id, current.position);
  };

  const wrap = (node: EngineNode, body: ReactNode, extraClass = "") => {
    const selected = selectedId === node.id || Boolean(multiSelected?.includes(node.id));
    const showDrop = drop?.target === node.id;
    const marker = markers?.[node.id];
    const roleHidden = preview ? preview[node.id]?.visible === false : false;
    const hidden = isHidden(node) || roleHidden;
    const why = hidden ? whyHidden(node, preview ?? null) : null;
    const comments = commentCounts?.[node.id] ?? 0;
    const heatHere = heat?.[node.id];
    const othersHere = cursors?.[node.id];
    return (
      <div
        key={node.id}
        className={`${styles.node} ${extraClass}`}
        data-node-id={node.id}
        data-selected={selected || undefined}
        data-hidden={hidden || undefined}
        data-marker={marker}
        data-locked={!node.anchor || undefined}
        data-heat={heatHere ? heatHere.level : undefined}
        data-others={othersHere?.length ? othersHere.join(", ") : undefined}
        data-tour={tourFocus === node.id || undefined}
        draggable={!readOnly && Boolean(node.anchor) && node.kind !== "root" && node.tag !== "sheet"}
        onDragStart={(e) => {
          e.stopPropagation();
          e.dataTransfer.setData(NODE_DRAG_TYPE, node.id);
          e.dataTransfer.effectAllowed = "move";
          (window as unknown as { __ingDrag?: string }).__ingDrag = node.id;
        }}
        onDragEnd={() => {
          (window as unknown as { __ingDrag?: string }).__ingDrag = undefined;
          setDrop(null);
        }}
        onDragOver={(e) => onDragOver(e, node)}
        onDragLeave={(e) => {
          if (e.currentTarget === e.target) setDrop((d) => (d?.target === node.id ? null : d));
        }}
        onDrop={(e) => onDrop(e, node)}
        onClick={(e) => {
          e.stopPropagation();
          onSelect(node.id, e.shiftKey || e.metaKey || e.ctrlKey);
        }}
      >
        {heatHere ? (
          <span className={styles.heatTag} data-testid="vd-heat" title={heatHere.label}>
            {heatHere.label}
          </span>
        ) : null}
        {othersHere?.length ? (
          <span className={styles.cursorTag} data-testid="vd-cursor">
            {othersHere.join(", ")}
          </span>
        ) : null}
        {marker ? (
          <span className={styles.markerTag} data-testid="vd-marker">
            {MARKER_WORDS[marker]}
          </span>
        ) : null}
        {commentCounts && comments > 0 ? (
          <button
            type="button"
            className={styles.commentDot}
            aria-label={`${comments} open comment${comments === 1 ? "" : "s"} on ${node.label || node.tag}`}
            onClick={(e) => {
              e.stopPropagation();
              onOpenComments?.(node.id);
            }}
          >
            {comments}
          </button>
        ) : null}
        {selected && node.kind !== "root" ? (
          <div className={styles.chipBar} data-testid="vd-chip-bar">
            {visibilityChips(node).map((c) => (
              <span key={c} className={styles.chip}>
                {c}
              </span>
            ))}
            {!node.anchor ? <span className={styles.chip}>Can&apos;t be changed safely</span> : null}
          </div>
        ) : null}
        {showDrop ? (
          <Note tone="info" as="div" className={styles.dropLabel} data-position={drop.position} data-ok={drop.ok || undefined} role="status" data-testid="vd-drop-label">
            {drop.label}
          </Note>
        ) : null}
        {hidden ? (
          why ? (
            <Tooltip label={why}>
              <span className={styles.hiddenTag} data-testid="vd-why-hidden" tabIndex={0}>
                {roleHidden && !isHidden(node) ? "Hidden for this role" : "Hidden"}, why?
              </span>
            </Tooltip>
          ) : (
            <span className={styles.hiddenTag}>Hidden</span>
          )
        ) : null}
        {body}
      </div>
    );
  };

  const renderField = (node: EngineNode) => {
    const value = valueText(record, node);
    return wrap(
      node,
      <div className="ofp-field" data-testid={`vd-field-${node.name}`}>
        <span className="ofp-label">
          <span className="ofp-label-text">{node.label}</span>
          {node.attrs.required === "1" || node.attrs.required === "True" ? <span className="ofp-required">*</span> : null}
        </span>
        <span className="ofp-value">
          {node.has_subview ? <span className="ofp-empty">{value || "Lines table"}</span> : value ? <span className="ofp-input-text">{value}</span> : <span className="ofp-empty">Empty</span>}
        </span>
      </div>,
    );
  };

  const renderChildren = (node: EngineNode) => node.children.map((c) => render(c));

  const render = (node: EngineNode): ReactNode => {
    switch (node.tag) {
      case "field":
        return renderField(node);
      case "sheet":
        return wrap(node, <div className="ofp-sheet">{renderChildren(node)}</div>, "ofp-sheet-bg");
      case "header":
        return wrap(node, <div className={styles.header}>{renderChildren(node)}</div>);
      case "group":
        return wrap(
          node,
          <section className="ofp-group">
            {node.attrs.string ? <div className="ofp-group-title">{node.attrs.string}</div> : null}
            <div className="ofp-group-body">
              {renderChildren(node)}
              {node.children.length === 0 ? <p className="ofp-empty">Drop fields here</p> : null}
            </div>
          </section>,
        );
      case "notebook": {
        const pages = node.children.filter((c) => c.tag === "page");
        const active = tabs[node.id] ?? pages[0]?.id;
        const page = pages.find((p) => p.id === active) ?? pages[0];
        return wrap(
          node,
          <div className="ofp-notebook">
            <div className="ofp-tabs" role="tablist">
              {pages.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  role="tab"
                  aria-selected={p.id === page?.id}
                  className={`ofp-tab ${p.id === page?.id ? "is-active" : ""}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setTabs((t) => ({ ...t, [node.id]: p.id }));
                    onSelect(p.id);
                  }}
                >
                  {p.attrs.string || p.label || "Tab"} <span className={styles.tabBadge}>{fieldCount(p)}</span>
                </button>
              ))}
            </div>
            {page ? render(page) : null}
          </div>,
        );
      }
      case "page":
        return wrap(
          node,
          <div className="ofp-tab-panel" role="tabpanel">
            {renderChildren(node)}
            {node.children.length === 0 ? <p className="ofp-empty">Nothing on this tab yet</p> : null}
          </div>,
        );
      case "button":
        return wrap(node, <span className={styles.button}>{node.label || "Button"}</span>);
      case "separator":
        return wrap(node, <div className="ofp-group-title">{node.label}</div>);
      case "label":
      case "h1":
      case "h2":
      case "h3":
      case "span":
      case "p":
      case "a":
        return node.children.length ? wrap(node, <div>{renderChildren(node)}</div>) : wrap(node, <span>{node.label}</span>);
      case "div":
      case "footer":
        return wrap(node, <div className={styles.box}>{renderChildren(node)}</div>);
      default:
        if (node.kind === "root") {
          if (node.tag === "list" || node.tag === "tree") return renderList(node);
          if (node.tag === "kanban") return wrap(node, <div className={styles.kanban}>{renderChildren(node)}</div>);
          return wrap(node, <div className="ofp-main">{renderChildren(node)}</div>);
        }
        return wrap(
          node,
          <div className={styles.block} data-testid="vd-block">
            {node.label}
          </div>,
        );
    }
  };

  const renderList = (node: EngineNode) => {
    const cols = node.children.filter((c) => c.tag === "field");
    return wrap(
      node,
      <div className={styles.listWrap}>
        <div className={styles.listHead} role="row">
          {node.children.map((c) =>
            c.tag === "field" ? (
              <div key={c.id} role="columnheader">
                {render(c)}
              </div>
            ) : (
              <div key={c.id}>{render(c)}</div>
            ),
          )}
        </div>
        {record ? (
          <div className={styles.listRow} role="row">
            {cols.map((c) => (
              <div key={c.id} role="cell">
                {valueText(record, c) || "\u00a0"}
              </div>
            ))}
          </div>
        ) : null}
      </div>,
    );
  };

  return (
    <div className={styles.canvasInner} data-testid="vd-canvas" onDragLeave={() => setDrop(null)}>
      {render(tree)}
    </div>
  );
}
