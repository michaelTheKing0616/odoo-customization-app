"use client";

import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "@/lib/cn";

export type TabItem = { value: string; label: string; content: React.ReactNode };

type TabsProps = {
  items: TabItem[];
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
  className?: string;
};

export function Tabs({ items, defaultValue, value, onValueChange, className }: TabsProps) {
  const initial = defaultValue ?? items[0]?.value;
  return (
    <TabsPrimitive.Root
      defaultValue={value === undefined ? initial : undefined}
      value={value}
      onValueChange={onValueChange}
      className={className}
      data-testid="tabs"
    >
      <TabsPrimitive.List className="flex flex-wrap gap-1 border-b border-border-subtle pb-2">
        {items.map((item) => (
          <TabsPrimitive.Trigger
            key={item.value}
            value={item.value}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm text-muted data-[state=active]:bg-accent-subtle data-[state=active]:text-ink",
            )}
          >
            {item.label}
          </TabsPrimitive.Trigger>
        ))}
      </TabsPrimitive.List>
      {items.map((item) => (
        <TabsPrimitive.Content key={item.value} value={item.value} className="pt-4">
          {item.content}
        </TabsPrimitive.Content>
      ))}
    </TabsPrimitive.Root>
  );
}
