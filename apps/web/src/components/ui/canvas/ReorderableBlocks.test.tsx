/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ReorderableBlocks,
  moveIndex,
  moveIndexById,
  pointInRect,
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

function dispatchDrop(
  target: Element,
  dataTransfer: Record<string, unknown>,
  clientX: number,
  clientY: number,
) {
  const event = new Event("drop", { bubbles: true, cancelable: true }) as Event & {
    clientX: number;
    clientY: number;
    dataTransfer: unknown;
  };
  Object.defineProperty(event, "clientX", { value: clientX });
  Object.defineProperty(event, "clientY", { value: clientY });
  Object.defineProperty(event, "dataTransfer", { value: dataTransfer });
  target.dispatchEvent(event);
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

  it("drop outside the canvas inserts nothing via onMove path", () => {
    const onMove = vi.fn();
    function MoveOnly() {
      const [items, setItems] = useState(INITIAL);
      return (
        <div>
          <ReorderableBlocks
            items={items}
            getId={(item) => item.id}
            onMove={(id, dir) => {
              onMove(id, dir);
              setItems((prev) => moveIndexById(prev, id, dir));
            }}
          >
            {(item) => <span>{item.label}</span>}
          </ReorderableBlocks>
          <div data-testid="order">{items.map((item) => item.id).join(",")}</div>
        </div>
      );
    }
    render(<MoveOnly />);
    const { items } = layoutCanvas();

    fireEvent.pointerDown(items[1], {
      button: 0,
      pointerId: 2,
      clientX: 20,
      clientY: 60,
    });
    fireEvent.pointerMove(items[1], { pointerId: 2, clientX: 20, clientY: 100 });
    // Release far outside the 200×120 canvas.
    fireEvent.pointerUp(items[1], { pointerId: 2, clientX: -50, clientY: -50 });

    expect(onMove).not.toHaveBeenCalled();
    expect(screen.getByTestId("order").textContent).toBe("a,b,c");
  });

  it("pointInRect rejects coordinates outside the canvas bounds", () => {
    const rect = { left: 0, right: 200, top: 0, bottom: 120 };
    expect(pointInRect(20, 20, rect)).toBe(true);
    expect(pointInRect(400, 400, rect)).toBe(false);
    expect(pointInRect(-1, 10, rect)).toBe(false);
  });

  it("accepts an external (palette) drop at the pointer insert index", () => {
    const onExternal = vi.fn();
    const canAccept = (dt: DataTransfer) => {
      const types = Array.from(dt.types || []);
      return types.includes("text/odoo-report-block") || Boolean(dt.getData("text/odoo-report-block"));
    };
    render(
      <ReorderableBlocks
        items={INITIAL}
        getId={(item) => item.id}
        externalDrop={{
          canAccept,
          onDrop: (dt, insertIndex) => {
            onExternal(dt.getData("text/odoo-report-block"), insertIndex);
          },
        }}
      >
        {(item) => <span>{item.label}</span>}
      </ReorderableBlocks>,
    );
    const { canvas, items } = layoutCanvas();
    stubRect(canvas, { x: 0, y: 0, w: 200, h: 120 });
    items.forEach((item, index) => {
      stubRect(item, { x: 0, y: index * 40, w: 200, h: 40 });
    });

    const dataTransfer = {
      types: ["text/odoo-report-block"],
      dropEffect: "copy",
      effectAllowed: "copy",
      getData: (type: string) => (type === "text/odoo-report-block" ? "heading" : ""),
      setData: vi.fn(),
    };

    // clientY 50 → midpoint of item 1 (y=40..80) → insert index 1
    dispatchDrop(canvas, dataTransfer, 20, 50);
    expect(onExternal).toHaveBeenCalledWith("heading", 1);
  });

  it("rejects an external drop whose pointer is outside the canvas", () => {
    const onExternal = vi.fn();
    const canAccept = (dt: DataTransfer) => {
      const types = Array.from(dt.types || []);
      return types.includes("text/odoo-report-block") || Boolean(dt.getData("text/odoo-report-block"));
    };
    render(
      <div>
        <ReorderableBlocks
          items={INITIAL}
          getId={(item) => item.id}
          externalDrop={{
            canAccept,
            onDrop: (dt, insertIndex) => {
              onExternal(dt.getData("text/odoo-report-block"), insertIndex);
            },
          }}
        >
          {(item) => <span>{item.label}</span>}
        </ReorderableBlocks>
        <div data-testid="outside-canvas">outside</div>
      </div>,
    );
    layoutCanvas();

    const dataTransfer = {
      types: ["text/odoo-report-block"],
      dropEffect: "copy",
      effectAllowed: "copy",
      getData: () => "heading",
      setData: vi.fn(),
    };

    // Drop on a node that is not the canvas — must not insert.
    dispatchDrop(screen.getByTestId("outside-canvas"), dataTransfer, 900, 900);
    expect(onExternal).not.toHaveBeenCalled();

    // Drop on the canvas with outside coordinates is also rejected.
    dispatchDrop(screen.getByTestId("reorderable-blocks"), dataTransfer, 900, 900);
    expect(onExternal).not.toHaveBeenCalled();
  });
});
