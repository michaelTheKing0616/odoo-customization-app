"use client";

import { useMemo, useRef, useState, type KeyboardEvent } from "react";
import type { EngineNode, EngineOp } from "@/lib/api/view-engine";
import { keyboardMove, nodeName, plainTag, type TreeIndex } from "@/lib/viewEngineOps";
import styles from "./ViewDesigner.module.css";

type Row = { node: EngineNode; depth: number; hasKids: boolean };

type LayersTreeProps = {
  tree: EngineNode;
  index: TreeIndex;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onOp: (op: EngineOp) => void;
  onRefused: (message: string) => void;
};

const ARROWS = ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"] as const;
type Arrow = (typeof ARROWS)[number];

/** Layers panel: an APG tree that mirrors the canvas, so everything works by keyboard. */
export function LayersTree({ tree, index, selectedId, onSelect, onOp, onRefused }: LayersTreeProps) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const listRef = useRef<HTMLUListElement>(null);

  const rows = useMemo(() => {
    const out: Row[] = [];
    const walk = (node: EngineNode, depth: number) => {
      const kids = node.children;
      out.push({ node, depth, hasKids: kids.length > 0 });
      if (!collapsed.has(node.id)) kids.forEach((k) => walk(k, depth + 1));
    };
    walk(tree, 0);
    return out;
  }, [tree, collapsed]);

  const focusRow = (id: string) => {
    onSelect(id);
    requestAnimationFrame(() => {
      listRef.current?.querySelector<HTMLElement>(`[data-row-id="${CSS.escape(id)}"]`)?.focus();
    });
  };

  const onKeyDown = (e: KeyboardEvent<HTMLElement>, row: Row) => {
    const i = rows.findIndex((r) => r.node.id === row.node.id);
    if (e.altKey && (ARROWS as readonly string[]).includes(e.key)) {
      e.preventDefault();
      const op = keyboardMove(index, row.node.id, e.key as Arrow);
      if (op) onOp(op);
      else onRefused(`${nodeName(row.node)} can't move that way.`);
      return;
    }
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        if (rows[i + 1]) focusRow(rows[i + 1].node.id);
        break;
      case "ArrowUp":
        e.preventDefault();
        if (rows[i - 1]) focusRow(rows[i - 1].node.id);
        break;
      case "ArrowRight":
        e.preventDefault();
        if (row.hasKids && collapsed.has(row.node.id)) {
          setCollapsed((c) => {
            const n = new Set(c);
            n.delete(row.node.id);
            return n;
          });
        } else if (row.hasKids) focusRow(row.node.children[0].id);
        break;
      case "ArrowLeft": {
        e.preventDefault();
        if (row.hasKids && !collapsed.has(row.node.id)) {
          setCollapsed((c) => new Set(c).add(row.node.id));
        } else {
          const parent = index.parentOf.get(row.node.id);
          if (parent) focusRow(parent);
        }
        break;
      }
      case "Home":
        e.preventDefault();
        focusRow(rows[0].node.id);
        break;
      case "End":
        e.preventDefault();
        focusRow(rows[rows.length - 1].node.id);
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        onSelect(row.node.id);
        break;
      default:
    }
  };

  return (
    <ul ref={listRef} role="tree" aria-label="Screen layers" className={styles.tree} data-testid="vd-layers">
      {rows.map((row) => {
        const selected = row.node.id === selectedId;
        const tabbable = selected || (!selectedId && row.node.id === tree.id);
        return (
          <li
            key={row.node.id}
            role="treeitem"
            aria-level={row.depth + 1}
            aria-selected={selected}
            aria-expanded={row.hasKids ? !collapsed.has(row.node.id) : undefined}
            tabIndex={tabbable ? 0 : -1}
            data-row-id={row.node.id}
            className={styles.treeRow}
            style={{ paddingInlineStart: 8 + row.depth * 14 }}
            onClick={() => onSelect(row.node.id)}
            onKeyDown={(e) => onKeyDown(e, row)}
          >
            <span className={styles.treeLabel}>{row.node.kind === "root" ? "Whole screen" : nodeName(row.node)}</span>
            <span className={styles.treeKind}>{row.node.kind === "block" ? "Odoo element" : plainTag(row.node.tag)}</span>
            {!row.node.anchor ? <span className={styles.treeKind}>locked</span> : null}
            {row.node.attrs.invisible === "1" || row.node.attrs.column_invisible === "1" ? (
              <span className={styles.treeKind}>hidden</span>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
