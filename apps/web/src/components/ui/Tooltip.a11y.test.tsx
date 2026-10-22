/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Tooltip, TooltipProvider, tooltipMotionStyle } from "@/components/ui/Tooltip";
import { DURATION_RANGE, REDUCED_MOTION_MAX_MS, REDUCED_MOTION_QUERY } from "@/components/ui/motion/constants";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function stubReducedMotion(reduce: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => ({
      matches: reduce && query === REDUCED_MOTION_QUERY,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
}

function parseTransition(transition: string | undefined) {
  return (transition ?? "")
    .split(/,(?![^(]*\))/)
    .map((part) => part.trim())
    .filter(Boolean)
    .map((part) => {
      const [property, duration] = part.split(/\s+/);
      return { property, ms: parseFloat(duration) };
    });
}

function renderTooltip(child: React.ReactElement = <button type="button">Trigger button</button>) {
  render(
    <TooltipProvider>
      <Tooltip label="Helper text">{child}</Tooltip>
    </TooltipProvider>,
  );
  return screen.getByRole("button", { name: "Trigger button" });
}

function focusOpen(trigger: HTMLElement) {
  trigger.focus();
  fireEvent.focus(trigger);
}

describe("Tooltip accessibility", () => {
  it("opens on mouse hover", async () => {
    const trigger = renderTooltip();
    fireEvent.pointerEnter(trigger, { pointerType: "mouse" });
    fireEvent.mouseEnter(trigger);
    fireEvent.mouseMove(trigger);

    await waitFor(() => {
      expect(screen.getByRole("tooltip")).toHaveTextContent("Helper text");
    });
  });

  it("links the open tooltip to the trigger with aria-describedby", async () => {
    const trigger = renderTooltip();
    expect(trigger).not.toHaveAttribute("aria-describedby");

    focusOpen(trigger);
    const tooltip = await screen.findByRole("tooltip");

    expect(tooltip.id).not.toBe("");
    expect(trigger.getAttribute("aria-describedby")).toBe(tooltip.id);
    expect(trigger).toHaveAccessibleDescription("Helper text");
  });

  it("drops the aria-describedby link after Escape closes the tooltip", async () => {
    const trigger = renderTooltip();
    focusOpen(trigger);
    await screen.findByRole("tooltip");

    fireEvent.keyDown(document, { key: "Escape", code: "Escape", bubbles: true });

    await waitFor(() => {
      expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    });
    expect(trigger).not.toHaveAttribute("aria-describedby");
  });

  it("keeps a describedby id the child already had", async () => {
    render(
      <>
        <p id="own-hint">Own hint</p>
        <TooltipProvider>
          <Tooltip label="Helper text">
            <button type="button" aria-describedby="own-hint">
              Trigger button
            </button>
          </Tooltip>
        </TooltipProvider>
      </>,
    );
    const trigger = screen.getByRole("button", { name: "Trigger button" });
    expect(trigger.getAttribute("aria-describedby")).toBe("own-hint");

    focusOpen(trigger);
    const tooltip = await screen.findByRole("tooltip");

    expect(trigger.getAttribute("aria-describedby")?.split(" ")).toEqual(["own-hint", tooltip.id]);
  });
});

describe("Tooltip motion", () => {
  it("animates transform and opacity under 300 ms by default", async () => {
    stubReducedMotion(false);
    const trigger = renderTooltip();
    focusOpen(trigger);
    const tooltip = await screen.findByRole("tooltip");

    const parts = parseTransition(tooltip.getAttribute("style")?.match(/transition:\s*([^;]+)/)?.[1]);
    expect(parts.map((part) => part.property)).toEqual(["transform", "opacity"]);
    for (const part of parts) expect(part.ms).toBeLessThan(300);
  });

  it("is opacity only at 200 ms or less when reduced motion is on", async () => {
    stubReducedMotion(true);
    const trigger = renderTooltip();
    focusOpen(trigger);
    const tooltip = await screen.findByRole("tooltip");

    const parts = parseTransition(tooltip.getAttribute("style")?.match(/transition:\s*([^;]+)/)?.[1]);
    expect(parts.map((part) => part.property)).toEqual(["opacity"]);
    expect(parts[0].ms).toBeLessThanOrEqual(REDUCED_MOTION_MAX_MS);
    expect(tooltip.style.transform).toBe("");
  });

  it("uses dropdown-range enter, a shorter exit, and no transform when reduced", () => {
    const enter = tooltipMotionStyle({ open: true, instant: undefined, transitionStatus: "starting" }, false);
    const exit = tooltipMotionStyle({ open: false, instant: undefined, transitionStatus: "ending" }, false);
    const reduced = tooltipMotionStyle({ open: true, instant: undefined, transitionStatus: "starting" }, true);

    const enterMs = parseTransition(enter.transition)[0].ms;
    const exitMs = parseTransition(exit.transition)[0].ms;
    expect(enterMs).toBeGreaterThanOrEqual(DURATION_RANGE.dropdownMs.min);
    expect(enterMs).toBeLessThanOrEqual(DURATION_RANGE.dropdownMs.max);
    expect(exitMs).toBeLessThan(enterMs);
    expect(enter.opacity).toBe(0);
    expect(enter.transform).toMatch(/^scale\(/);
    expect(enter.transition).not.toContain("all");
    expect(reduced.transform).toBeUndefined();
    expect(parseTransition(reduced.transition).map((part) => part.property)).toEqual(["opacity"]);
  });
});
