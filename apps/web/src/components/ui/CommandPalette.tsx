"use client";

import { Command } from "cmdk";
import { Search } from "@/components/ui/icons";
import { cn } from "@/lib/cn";

export type CommandItem = {
  id: string;
  label: string;
  group: string;
  keywords?: string[];
  onSelect: () => void;
};

type CommandPaletteProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: CommandItem[];
  dynamicItems?: CommandItem[];
  onSearchChange?: (value: string) => void;
  placeholder?: string;
};

export function CommandPalette({
  open,
  onOpenChange,
  items,
  dynamicItems = [],
  onSearchChange,
  placeholder = "Search navigation, models, or ask Expert…",
}: CommandPaletteProps) {
  if (!open) return null;

  const allItems = [...items, ...dynamicItems];
  const groups = allItems.reduce<Record<string, CommandItem[]>>((acc, item) => {
    acc[item.group] = acc[item.group] ?? [];
    acc[item.group].push(item);
    return acc;
  }, {});

  return (
    <div className="fixed inset-0 z-[80]">
      <button
        type="button"
        className="absolute inset-0 bg-black/40"
        aria-label="Close command palette"
        onClick={() => onOpenChange(false)}
      />
      <div className="absolute left-1/2 top-[12vh] w-full max-w-xl -translate-x-1/2 px-4">
        <Command
          className="overflow-hidden rounded-lg border border-border-subtle bg-surface-raised shadow-overlay"
          data-testid="command-palette"
          onValueChange={onSearchChange}
        >
          <div className="flex items-center gap-2 border-b border-border-subtle px-3">
            <Search className="h-4 w-4 text-muted" />
            <Command.Input
              placeholder={placeholder}
              className="h-11 w-full bg-transparent text-sm outline-none"
              autoFocus
            />
          </div>
          <Command.List className="max-h-80 overflow-auto p-2">
            <Command.Empty className="px-3 py-6 text-center text-sm text-muted">
              No results.
            </Command.Empty>
            {Object.entries(groups).map(([group, groupItems]) => (
              <Command.Group
                key={group}
                heading={group}
                className="[&_[cmdk-group-heading]]:px-2 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-xs [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-muted"
              >
                {groupItems.map((item) => (
                  <Command.Item
                    key={item.id}
                    value={`${item.label} ${item.keywords?.join(" ") ?? ""}`}
                    onSelect={() => {
                      item.onSelect();
                      onOpenChange(false);
                    }}
                    className={cn(
                      "cursor-pointer rounded-md px-2 py-2 text-sm aria-selected:bg-accent-subtle",
                    )}
                  >
                    {item.label}
                  </Command.Item>
                ))}
              </Command.Group>
            ))}
          </Command.List>
        </Command>
      </div>
    </div>
  );
}
