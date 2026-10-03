/** @vitest-environment jsdom */
import React from "react";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { Tabs } from "@/components/ui/Tabs";

afterEach(() => {
  cleanup();
});

const items = [
  { value: "one", label: "Tab One", content: <p>Panel one</p> },
  { value: "two", label: "Tab Two", content: <p>Panel two</p> },
  { value: "three", label: "Tab Three", content: <p>Panel three</p> },
];

function getTabButtons() {
  return screen.getAllByRole("tab");
}

describe("Tabs characterization", () => {
  it("exposes data-testid tabs on the root", () => {
    render(<Tabs items={items} defaultValue="one" />);
    expect(screen.getByTestId("tabs")).toBeInTheDocument();
  });

  it("sets aria-selected on the active tab", () => {
    render(<Tabs items={items} defaultValue="two" />);
    const tabs = getTabButtons();
    expect(tabs[0]).toHaveAttribute("aria-selected", "false");
    expect(tabs[1]).toHaveAttribute("aria-selected", "true");
    expect(tabs[2]).toHaveAttribute("aria-selected", "false");
  });

  it("uses roving tabindex so only the selected tab is tabbable", async () => {
    render(<Tabs items={items} defaultValue="two" />);
    const tabs = getTabButtons();
    tabs[1].focus();

    await waitFor(() => {
      const current = getTabButtons();
      const tabbable = current.filter((tab) => tab.getAttribute("tabindex") === "0");
      expect(tabbable).toHaveLength(1);
      expect(tabbable[0]).toHaveAttribute("aria-selected", "true");
    });

    const current = getTabButtons();
    expect(current[0]).toHaveAttribute("tabindex", "-1");
    expect(current[2]).toHaveAttribute("tabindex", "-1");
  });

  it("navigates between tabs with arrow keys and updates selection", async () => {
    render(<Tabs items={items} defaultValue="one" />);
    const tabs = getTabButtons();
    tabs[0].focus();

    fireEvent.keyDown(tabs[0], { key: "ArrowRight", code: "ArrowRight", bubbles: true });

    await waitFor(() => {
      const tabsAfter = getTabButtons();
      expect(tabsAfter[0]).toHaveAttribute("aria-selected", "false");
      expect(tabsAfter[1]).toHaveAttribute("aria-selected", "true");
      expect(tabsAfter[1]).toHaveAttribute("tabindex", "0");
      expect(tabsAfter[0]).toHaveAttribute("tabindex", "-1");
    });
  });
});
