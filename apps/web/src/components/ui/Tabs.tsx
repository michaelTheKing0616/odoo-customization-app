"use client";

import { Tabs as BaseTabs } from "@base-ui/react/tabs";
import { cn } from "@/lib/cn";

export type TabItem = { value: string; label: string; content: React.ReactNode };

type TabsProps = {
  items: TabItem[];
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  className?: string;
};

const TAB_KEYS = new Set(["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"]);

function activateFocusedTab() {
  const active = document.activeElement;
  if (!(active instanceof HTMLElement)) return;
  if (active.getAttribute("role") !== "tab") return;
  if (active.getAttribute("aria-selected") === "true") return;
  active.click();
}

export function Tabs({ items, defaultValue, value, onValueChange, className }: TabsProps) {
  const initial = defaultValue ?? items[0]?.value;
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
        className="flex flex-wrap gap-1 border-b border-border-subtle pb-2"
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
            )}
          >
            {item.label}
          </BaseTabs.Tab>
        ))}
      </BaseTabs.List>
      {items.map((item) => (
        <BaseTabs.Panel key={item.value} value={item.value} className="pt-4">
          {item.content}
        </BaseTabs.Panel>
      ))}
    </BaseTabs.Root>
  );
}
