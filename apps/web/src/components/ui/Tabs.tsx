"use client";

import type * as React from "react";
import { Tabs as BaseTabs } from "@base-ui/react/tabs";
import { cn } from "@/lib/cn";
import { DURATION, EASE_ENTER_EXIT, MOTION_PROPERTIES } from "@/components/ui/motion/constants";
import { usePrefersReducedMotion } from "@/components/ui/motion/usePrefersReducedMotion";

export type TabItem = { value: string; label: string; content: React.ReactNode };

type TabsProps = {
  items: TabItem[];
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  className?: string;
};

const TAB_KEYS = new Set(["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"]);

const INDICATOR_THICKNESS_PX = 2;

const FOCUS_RING = "outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2";

type TabsIndicatorMotionState = Pick<BaseTabs.Indicator.State, "activeTabPosition" | "activeTabSize">;

/**
 * Indicator style per state. The bar is 1px wide and reaches the active tab through
 * translate + scaleX, so a move between tabs of different widths animates transform only.
 * Reduced motion drops the transform transition and keeps opacity only.
 */
export function tabsIndicatorMotionStyle(state: TabsIndicatorMotionState, reduced: boolean): React.CSSProperties {
  const { activeTabPosition: position, activeTabSize: size } = state;
  const properties = reduced ? ["opacity"] : MOTION_PROPERTIES;
  const durationMs = reduced ? DURATION.reducedMotionMs : DURATION.dropdownMs;
  const x = position?.left ?? 0;
  const y = (position?.top ?? 0) + (size?.height ?? 0) - INDICATOR_THICKNESS_PX;
  return {
    opacity: size ? 1 : 0,
    transform: `translate(${x}px, ${y}px) scaleX(${size?.width ?? 0})`,
    transformOrigin: "0 0",
    transition: properties.map((property) => `${property} ${durationMs}ms ${EASE_ENTER_EXIT.css}`).join(", "),
  };
}

function activateFocusedTab() {
  const active = document.activeElement;
  if (!(active instanceof HTMLElement)) return;
  if (active.getAttribute("role") !== "tab") return;
  if (active.getAttribute("aria-selected") === "true") return;
  active.click();
}

export function Tabs({ items, defaultValue, value, onValueChange, className }: TabsProps) {
  const initial = defaultValue ?? items[0]?.value;
  const reduced = usePrefersReducedMotion();
  return (
    <BaseTabs.Root
      defaultValue={value === undefined ? initial : undefined}
      value={value}
      onValueChange={(nextValue) => onValueChange?.(String(nextValue))}
      className={className}
      data-testid="tabs"
    >
      <BaseTabs.List
        activateOnFocus
        className="relative flex flex-wrap gap-1 border-b border-border-subtle pb-2"
        onKeyDown={(event) => {
          if (!TAB_KEYS.has(event.key)) return;
          // Base UI moves roving focus on these keys and selects on focus in jsdom.
          // In the browser the focus move does not select, so activate the newly
          // focused tab after that focus microtask.
          queueMicrotask(() => {
            queueMicrotask(activateFocusedTab);
          });
        }}
      >
        {items.map((item) => (
          <BaseTabs.Tab
            key={item.value}
            value={item.value}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm text-muted data-active:bg-accent-subtle data-active:text-ink",
              FOCUS_RING,
            )}
          >
            {item.label}
          </BaseTabs.Tab>
        ))}
        <BaseTabs.Indicator
          data-testid="tabs-indicator"
          className="pointer-events-none absolute left-0 top-0 h-0.5 w-px bg-accent"
          style={(state) => tabsIndicatorMotionStyle(state, reduced)}
        />
      </BaseTabs.List>
      {items.map((item) => (
        <BaseTabs.Panel key={item.value} value={item.value} className={cn("rounded-md pt-4", FOCUS_RING)}>
          {item.content}
        </BaseTabs.Panel>
      ))}
    </BaseTabs.Root>
  );
}
