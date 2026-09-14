import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  autoScrollFromPointer,
  findScrollableAncestors,
} from "./drag-auto-scroll";

describe("drag-auto-scroll", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    vi.stubGlobal("scrollBy", vi.fn());
    document.elementFromPoint = () => null;
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("finds overflow ancestors", () => {
    const outer = document.createElement("div");
    outer.style.overflowY = "auto";
    Object.defineProperty(outer, "scrollHeight", { value: 500, configurable: true });
    Object.defineProperty(outer, "clientHeight", { value: 100, configurable: true });
    const inner = document.createElement("div");
    outer.appendChild(inner);
    document.body.appendChild(outer);
    expect(findScrollableAncestors(inner)).toContain(outer);
  });

  it("does not scroll the window when a nested scroller is under the pointer", () => {
    Object.defineProperty(window, "innerHeight", { value: 800, configurable: true });
    Object.defineProperty(window, "innerWidth", { value: 1200, configurable: true });
    const box = document.createElement("div");
    box.style.overflowY = "auto";
    Object.defineProperty(box, "scrollHeight", { value: 800, configurable: true });
    Object.defineProperty(box, "clientHeight", { value: 200, configurable: true });
    box.scrollTop = 50;
    box.getBoundingClientRect = () =>
      ({
        top: 100,
        bottom: 300,
        left: 0,
        right: 400,
        width: 400,
        height: 200,
        x: 0,
        y: 100,
        toJSON: () => ({}),
      }) as DOMRect;
    document.body.appendChild(box);
    document.elementFromPoint = () => box;

    // Near viewport bottom (would have scrolled window before) but inside nested box mid-area.
    autoScrollFromPointer(50, 200);
    expect(window.scrollBy).not.toHaveBeenCalled();
  });

  it("scrolls a nested overflow container near its bottom edge", () => {
    Object.defineProperty(window, "innerHeight", { value: 900, configurable: true });
    Object.defineProperty(window, "innerWidth", { value: 1200, configurable: true });
    const box = document.createElement("div");
    box.style.overflowY = "auto";
    Object.defineProperty(box, "scrollHeight", { value: 800, configurable: true });
    Object.defineProperty(box, "clientHeight", { value: 200, configurable: true });
    box.scrollTop = 0;
    box.getBoundingClientRect = () =>
      ({
        top: 100,
        bottom: 300,
        left: 0,
        right: 400,
        width: 400,
        height: 200,
        x: 0,
        y: 100,
        toJSON: () => ({}),
      }) as DOMRect;
    document.body.appendChild(box);
    document.elementFromPoint = () => box;

    autoScrollFromPointer(50, 280);
    expect(box.scrollTop).toBeGreaterThan(0);
    expect(window.scrollBy).not.toHaveBeenCalled();
  });

  it("scrolls window only when no nested scroller is under the pointer", () => {
    Object.defineProperty(window, "innerHeight", { value: 800, configurable: true });
    Object.defineProperty(window, "innerWidth", { value: 1200, configurable: true });
    document.elementFromPoint = () => document.body;
    autoScrollFromPointer(100, 790);
    expect(window.scrollBy).toHaveBeenCalled();
    const [, dy] = (window.scrollBy as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(dy).toBeGreaterThan(0);
  });
});
