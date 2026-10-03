"use client";

import {
  useCallback,
  useRef,
  useState,
  type HTMLAttributes,
  type KeyboardEvent,
  type MouseEvent,
  type PointerEvent,
  type ReactNode,
  type Ref,
} from "react";
import { cn } from "@/lib/cn";

export const REORDER_DRAG_THRESHOLD_PX = 4;

export type ReorderableBlockMeta = {
  isDragging: boolean;
  dropIndex: number | null;
  isDropTarget: boolean;
};

export type ReorderableBlocksProps<T> = {
  items: T[];
  getId: (item: T) => string;
  children: (item: T, index: number, meta: ReorderableBlockMeta) => ReactNode;
  /** Destination index in the current list (0..length-1). */
  onReorder?: (fromIndex: number, toIndex: number) => void;
  /** One-step move used by keyboard arrows and existing up/down buttons. */
  onMove?: (id: string, dir: -1 | 1) => void;
  disabled?: boolean;
  empty?: ReactNode;
  footer?: ReactNode;
  className?: string;
  itemClassName?: string | ((item: T, index: number) => string);
  as?: "div" | "ul";
  itemAs?: "div" | "li";
  listProps?: HTMLAttributes<HTMLElement> & {
    ref?: Ref<HTMLElement | null>;
    "data-testid"?: string;
  };
  itemProps?: (
    item: T,
    index: number,
  ) => HTMLAttributes<HTMLElement> & {
    "data-canvas-field"?: string;
    "data-field-id"?: string;
    "data-testid"?: string;
  };
};

export function pointInRect(
  x: number,
  y: number,
  rect: Pick<DOMRect, "left" | "right" | "top" | "bottom">,
): boolean {
  return x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom;
}

export function insertIndexFromClientY(
  clientY: number,
  rects: Array<Pick<DOMRect, "top" | "height">>,
): number {
  for (let i = 0; i < rects.length; i += 1) {
    const rect = rects[i];
    if (clientY < rect.top + rect.height / 2) return i;
  }
  return rects.length;
}

/** Convert an insert index (0..length) into a final destination index. */
export function destIndexFromInsert(fromIndex: number, insertIndex: number): number {
  if (insertIndex > fromIndex) return insertIndex - 1;
  return insertIndex;
}

export function moveIndex<T>(items: readonly T[], fromIndex: number, toIndex: number): T[] {
  if (
    fromIndex === toIndex ||
    fromIndex < 0 ||
    toIndex < 0 ||
    fromIndex >= items.length ||
    toIndex >= items.length
  ) {
    return items.slice();
  }
  const next = items.slice();
  const [item] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, item);
  return next;
}

export function moveIndexById<T extends { id: string }>(
  items: readonly T[],
  id: string,
  dir: -1 | 1,
): T[] {
  const fromIndex = items.findIndex((item) => item.id === id);
  if (fromIndex < 0) return items.slice();
  return moveIndex(items, fromIndex, fromIndex + dir);
}

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target.isContentEditable;
}

function isNestedControl(target: EventTarget | null, itemEl: HTMLElement): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const control = target.closest("button, input, textarea, select, a, [data-no-reorder]");
  if (!(control instanceof HTMLElement)) return false;
  return control !== itemEl && itemEl.contains(control);
}

function itemRects(list: HTMLElement): DOMRect[] {
  return Array.from(list.querySelectorAll<HTMLElement>("[data-reorder-item]")).map((el) =>
    el.getBoundingClientRect(),
  );
}

/**
 * One canvas reorder primitive: pointer drag + keyboard arrows.
 * A pointer-up outside this list inserts nothing.
 */
export function ReorderableBlocks<T>({
  items,
  getId,
  children,
  onReorder,
  onMove,
  disabled = false,
  empty,
  footer,
  className,
  itemClassName,
  as = "div",
  itemAs = "div",
  listProps,
  itemProps,
}: ReorderableBlocksProps<T>) {
  const listRef = useRef<HTMLElement | null>(null);
  const dragRef = useRef<{
    id: string;
    fromIndex: number;
    pointerId: number;
    startX: number;
    startY: number;
    active: boolean;
  } | null>(null);
  const suppressClickRef = useRef(false);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dropIndex, setDropIndex] = useState<number | null>(null);

  const canReorder = !disabled && Boolean(onReorder || onMove);

  const resetDrag = useCallback(() => {
    dragRef.current = null;
    setDraggingId(null);
    setDropIndex(null);
  }, []);

  const applyStepMove = useCallback(
    (id: string, dir: -1 | 1) => {
      if (onMove) {
        onMove(id, dir);
        return;
      }
      if (!onReorder) return;
      const fromIndex = items.findIndex((item) => getId(item) === id);
      const toIndex = fromIndex + dir;
      if (fromIndex < 0 || toIndex < 0 || toIndex >= items.length) return;
      onReorder(fromIndex, toIndex);
    },
    [getId, items, onMove, onReorder],
  );

  const applyPointerReorder = useCallback(
    (fromIndex: number, toIndex: number) => {
      if (fromIndex === toIndex) return;
      if (onReorder) {
        onReorder(fromIndex, toIndex);
        return;
      }
      if (!onMove) return;
      const id = items[fromIndex] ? getId(items[fromIndex]) : null;
      if (!id) return;
      const dir: -1 | 1 = toIndex > fromIndex ? 1 : -1;
      let current = fromIndex;
      while (current !== toIndex) {
        onMove(id, dir);
        current += dir;
      }
    },
    [getId, items, onMove, onReorder],
  );

  function onItemPointerDown(event: PointerEvent<HTMLElement>, index: number) {
    if (!canReorder || event.button !== 0) return;
    const itemEl = event.currentTarget;
    if (isNestedControl(event.target, itemEl)) return;
    if (isEditableTarget(event.target)) return;
    dragRef.current = {
      id: getId(items[index]),
      fromIndex: index,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      active: false,
    };
    try {
      itemEl.setPointerCapture?.(event.pointerId);
    } catch {
      /* happy-dom and some jsdom builds omit capture */
    }
  }

  function onItemPointerMove(event: PointerEvent<HTMLElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    if (!drag.active && Math.hypot(dx, dy) < REORDER_DRAG_THRESHOLD_PX) return;
    if (!drag.active) {
      drag.active = true;
      setDraggingId(drag.id);
    }
    event.preventDefault();
    const list = listRef.current;
    if (!list) return;
    const insert = insertIndexFromClientY(event.clientY, itemRects(list));
    setDropIndex(insert);
  }

  function onItemPointerUp(event: PointerEvent<HTMLElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const list = listRef.current;
    const wasActive = drag.active;
    const fromIndex = drag.fromIndex;
    const { clientX, clientY } = event;
    resetDrag();
    if (!wasActive || !list) return;
    suppressClickRef.current = true;
    // Reject any pointer-up that is not inside this canvas list.
    if (!pointInRect(clientX, clientY, list.getBoundingClientRect())) {
      return;
    }
    const insert = insertIndexFromClientY(clientY, itemRects(list));
    const toIndex = destIndexFromInsert(fromIndex, insert);
    applyPointerReorder(fromIndex, toIndex);
  }

  function onItemPointerCancel(event: PointerEvent<HTMLElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    resetDrag();
  }

  function onItemKeyDown(
    event: KeyboardEvent<HTMLElement>,
    index: number,
    userHandler?: HTMLAttributes<HTMLElement>["onKeyDown"],
  ) {
    userHandler?.(event);
    if (event.defaultPrevented || !canReorder) return;
    if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
    if (isEditableTarget(event.target)) return;
    event.preventDefault();
    event.stopPropagation();
    applyStepMove(getId(items[index]), event.key === "ArrowDown" ? 1 : -1);
  }

  function onItemClickCapture(event: MouseEvent<HTMLElement>) {
    if (!suppressClickRef.current) return;
    suppressClickRef.current = false;
    event.preventDefault();
    event.stopPropagation();
  }

  const ListTag = as;
  const ItemTag = itemAs;

  return (
    <ListTag
      {...listProps}
      ref={(node) => {
        listRef.current = node;
        const forwarded = listProps?.ref;
        if (typeof forwarded === "function") forwarded(node);
        else if (forwarded) forwarded.current = node;
      }}
      className={cn(className, listProps?.className)}
      data-testid={listProps?.["data-testid"] ?? "reorderable-blocks"}
      data-reorder-canvas=""
    >
      {items.map((item, index) => {
        const id = getId(item);
        const extra = itemProps?.(item, index) ?? {};
        const resolvedItemClass =
          typeof itemClassName === "function" ? itemClassName(item, index) : itemClassName;
        const meta: ReorderableBlockMeta = {
          isDragging: draggingId === id,
          dropIndex,
          isDropTarget: dropIndex === index,
        };
        const {
          className: extraClass,
          onKeyDown,
          onPointerDown,
          onPointerMove,
          onPointerUp,
          onPointerCancel,
          onClick,
          ...restExtra
        } = extra;
        return (
          <ItemTag
            key={id}
            {...restExtra}
            data-reorder-item=""
            data-reorder-id={id}
            data-dragging={meta.isDragging ? "true" : undefined}
            aria-grabbed={meta.isDragging}
            tabIndex={restExtra.tabIndex ?? (canReorder ? 0 : undefined)}
            className={cn(resolvedItemClass, extraClass)}
            onClick={(event) => {
              onItemClickCapture(event);
              if (event.defaultPrevented) return;
              onClick?.(event);
            }}
            onPointerDown={(event) => {
              onPointerDown?.(event);
              if (event.defaultPrevented) return;
              onItemPointerDown(event, index);
            }}
            onPointerMove={(event) => {
              onPointerMove?.(event);
              onItemPointerMove(event);
            }}
            onPointerUp={(event) => {
              onPointerUp?.(event);
              onItemPointerUp(event);
            }}
            onPointerCancel={(event) => {
              onPointerCancel?.(event);
              onItemPointerCancel(event);
            }}
            onKeyDown={(event) => onItemKeyDown(event, index, onKeyDown)}
          >
            {children(item, index, meta)}
          </ItemTag>
        );
      })}
      {items.length === 0 ? empty : null}
      {footer}
    </ListTag>
  );
}
