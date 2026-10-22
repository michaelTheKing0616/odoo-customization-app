/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Tabs, tabsIndicatorMotionStyle } from "@/components/ui/Tabs";
import { DURATION_RANGE, REDUCED_MOTION_MAX_MS, REDUCED_MOTION_QUERY } from "@/components/ui/motion/constants";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const items = [
  { value: "one", label: "Tab One", content: <p>Panel one</p> },
  { value: "two", label: "Tab Two", content: <p>Panel two</p> },
  { value: "three", label: "Tab Three", content: <p>Panel three</p> },
];

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

function pressOn(tab: HTMLElement, key: string) {
  tab.focus();
  fireEvent.keyDown(tab, { key, code: key, bubbles: true });
}

async function expectSelected(label: string) {
  await waitFor(() => {
    const selected = screen.getAllByRole("tab").filter((tab) => tab.getAttribute("aria-selected") === "true");
    expect(selected).toHaveLength(1);
    expect(selected[0]).toHaveTextContent(label);
    expect(selected[0]).toHaveAttribute("tabindex", "0");
  });
}

const placed = { activeTabPosition: { left: 12, right: 0, top: 4, bottom: 0 }, activeTabSize: { width: 80, height: 32 } };

describe("Tabs roles and relationships", () => {
  it("renders a tablist of tabs and links the selected tab to its panel both ways", () => {
    render(<Tabs items={items} defaultValue="two" />);
    expect(screen.getByRole("tablist")).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(3);

    const selected = screen.getByRole("tab", { name: "Tab Two" });
    const panel = screen.getByRole("tabpanel");
    expect(panel).toHaveTextContent("Panel two");
    expect(panel.id).not.toBe("");
    expect(selected).toHaveAttribute("aria-controls", panel.id);
    expect(panel).toHaveAttribute("aria-labelledby", selected.id);
  });

  it("does not point aria-controls at a panel that is not rendered", () => {
    render(<Tabs items={items} defaultValue="one" />);
    for (const tab of screen.getAllByRole("tab")) {
      const controls = tab.getAttribute("aria-controls");
      if (controls) expect(document.getElementById(controls)).not.toBeNull();
    }
  });

  it("hides the indicator from assistive tech", () => {
    render(<Tabs items={items} />);
    expect(screen.getByTestId("tabs-indicator")).toHaveAttribute("role", "presentation");
  });
});

describe("Tabs keyboard navigation", () => {
  it("moves selection back with ArrowLeft", async () => {
    render(<Tabs items={items} defaultValue="two" />);
    pressOn(screen.getByRole("tab", { name: "Tab Two" }), "ArrowLeft");
    await expectSelected("Tab One");
  });

  it("jumps to the last tab with End and the first tab with Home", async () => {
    render(<Tabs items={items} defaultValue="one" />);
    pressOn(screen.getByRole("tab", { name: "Tab One" }), "End");
    await expectSelected("Tab Three");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Panel three");

    pressOn(screen.getByRole("tab", { name: "Tab Three" }), "Home");
    await expectSelected("Tab One");
    expect(screen.getByRole("tabpanel")).toHaveTextContent("Panel one");
  });

  it("reports keyboard selection to a controlled caller", async () => {
    const onValueChange = vi.fn();
    function Controlled() {
      const [value, setValue] = React.useState("one");
      return (
        <Tabs
          items={items}
          value={value}
          onValueChange={(next) => {
            onValueChange(next);
            setValue(next);
          }}
        />
      );
    }
    render(<Controlled />);
    pressOn(screen.getByRole("tab", { name: "Tab One" }), "ArrowRight");
    await expectSelected("Tab Two");
    expect(onValueChange).toHaveBeenCalledWith("two");
  });

  it("gives tabs and the panel a focus-visible ring on the accent token", () => {
    render(<Tabs items={items} />);
    for (const el of [...screen.getAllByRole("tab"), screen.getByRole("tabpanel")]) {
      expect(el.className).toContain("focus-visible:ring-2");
      expect(el.className).toContain("focus-visible:ring-accent");
      expect(el.className).toContain("outline-none");
    }
  });
});

describe("Tabs indicator motion", () => {
  it("animates transform and opacity under 300 ms by default", () => {
    stubReducedMotion(false);
    render(<Tabs items={items} />);
    const indicator = screen.getByTestId("tabs-indicator");
    const parts = parseTransition(indicator.style.transition);
    expect(parts.map((part) => part.property)).toEqual(["transform", "opacity"]);
    for (const part of parts) expect(part.ms).toBeLessThan(300);
  });

  it("is opacity only at 200 ms or less when reduced motion is on", () => {
    stubReducedMotion(true);
    render(<Tabs items={items} />);
    const parts = parseTransition(screen.getByTestId("tabs-indicator").style.transition);
    expect(parts.map((part) => part.property)).toEqual(["opacity"]);
    expect(parts[0].ms).toBeLessThanOrEqual(REDUCED_MOTION_MAX_MS);
  });

  it("reaches the active tab through transform only, in the dropdown duration range", () => {
    const style = tabsIndicatorMotionStyle(placed, false);
    expect(style.transform).toBe("translate(12px, 34px) scaleX(80)");
    expect(style.opacity).toBe(1);
    expect(style).not.toHaveProperty("width");
    expect(style).not.toHaveProperty("left");
    expect(style.transition).not.toContain("all");
    const ms = parseTransition(style.transition)[0].ms;
    expect(ms).toBeGreaterThanOrEqual(DURATION_RANGE.dropdownMs.min);
    expect(ms).toBeLessThanOrEqual(DURATION_RANGE.dropdownMs.max);
  });

  it("stays invisible until Base UI has measured the active tab", () => {
    const style = tabsIndicatorMotionStyle({ activeTabPosition: null, activeTabSize: null }, false);
    expect(style.opacity).toBe(0);
  });
});
