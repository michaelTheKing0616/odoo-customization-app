/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ReorderableBlocks,
  moveIndex,
  moveIndexById,
} from "./ReorderableBlocks";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

type Block = { id: string; label: string };

const INITIAL: Block[] = [
  { id: "a", label: "Alpha" },
  { id: "b", label: "Beta" },
  { id: "c", label: "Gamma" },
];

function stubRect(
  el: Element,
  rect: { x: number; y: number; w: number; h: number },
) {
  vi.spyOn(el, "getBoundingClientRect").mockReturnValue({
    x: rect.x,
    y: rect.y,
    width: rect.w,
    height: rect.h,
    top: rect.y,
    left: rect.x,
    right: rect.x + rect.w,
    bottom: rect.y + rect.h,
    toJSON: () => ({}),
  } as DOMRect);
}

function layoutCanvas() {
  const canvas = screen.getByTestId("reorderable-blocks");
  stubRect(canvas, { x: 0, y: 0, w: 200, h: 120 });
  const items = canvas.querySelectorAll("[data-reorder-item]");
  items.forEach((item, index) => {
    stubRect(item, { x: 0, y: index * 40, w: 200, h: 40 });
  });
  return { canvas, items };
}

function Harness({
  onReorder,
  onMove,
}: {
  onReorder?: (from: number, to: number) => void;
  onMove?: (id: string, dir: -1 | 1) => void;
}) {
  const [items, setItems] = useState(INITIAL);
  return (
    <div>
      <ReorderableBlocks
        items={items}
        getId={(item) => item.id}
        onReorder={(from, to) => {
          onReorder?.(from, to);
          setItems((prev) => moveIndex(prev, from, to));
        }}
        onMove={(id, dir) => {
          onMove?.(id, dir);
          setItems((prev) => moveIndexById(prev, id, dir));
        }}
      >
        {(item) => <span>{item.label}</span>}
      </ReorderableBlocks>
      <div data-testid="order">{items.map((item) => item.id).join(",")}</div>
    </div>
  );
}

describe("ReorderableBlocks", () => {
  it("does not change order when the drop is outside the canvas", () => {
    const onReorder = vi.fn();
    render(<Harness onReorder={onReorder} />);
    const { items } = layoutCanvas();

    fireEvent.pointerDown(items[0], {
      button: 0,
      pointerId: 1,
      clientX: 20,
      clientY: 20,
    });
    fireEvent.pointerMove(items[0], { pointerId: 1, clientX: 20, clientY: 80 });
    fireEvent.pointerUp(items[0], { pointerId: 1, clientX: 400, clientY: 400 });

    expect(onReorder).not.toHaveBeenCalled();
    expect(screen.getByTestId("order").textContent).toBe("a,b,c");
  });

  it("reorders the focused block with keyboard arrows", () => {
    const onMove = vi.fn();
    render(<Harness onMove={onMove} />);
    const first = screen.getByTestId("reorderable-blocks").querySelector("[data-reorder-id='a']");
    expect(first).toBeTruthy();
    (first as HTMLElement).focus();
    fireEvent.keyDown(first as HTMLElement, { key: "ArrowDown" });
    expect(onMove).toHaveBeenCalledWith("a", 1);
    expect(screen.getByTestId("order").textContent).toBe("b,a,c");

    const moved = screen.getByTestId("reorderable-blocks").querySelector("[data-reorder-id='a']");
    fireEvent.keyDown(moved as HTMLElement, { key: "ArrowUp" });
    expect(onMove).toHaveBeenCalledWith("a", -1);
    expect(screen.getByTestId("order").textContent).toBe("a,b,c");
  });

  it("reorders when the pointer is released inside the canvas", () => {
    const onReorder = vi.fn();
    render(<Harness onReorder={onReorder} />);
    const { items } = layoutCanvas();

    fireEvent.pointerDown(items[0], {
      button: 0,
      pointerId: 1,
      clientX: 20,
      clientY: 20,
    });
    fireEvent.pointerMove(items[0], { pointerId: 1, clientX: 20, clientY: 90 });
    fireEvent.pointerUp(items[0], { pointerId: 1, clientX: 20, clientY: 90 });

    expect(onReorder).toHaveBeenCalled();
    expect(screen.getByTestId("order").textContent).not.toBe("a,b,c");
  });
});
