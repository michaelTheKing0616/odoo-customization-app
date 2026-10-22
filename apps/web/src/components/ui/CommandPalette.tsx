"use client";

import * as React from "react";
import { Command } from "cmdk";
import { Search } from "@/components/ui/icons";
import { cn } from "@/lib/cn";

export type CommandItem = {
  id: string;
  label: string;
  group: string;
  keywords?: string[];
  /** One-line detail shown in the preview pane (85). */
  detail?: string;
  /** Per-item actions: pick the item, press Tab (or Mod+K) to see only these (85). */
  actions?: Array<{ id: string; label: string; onSelect: () => void }>;
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
  placeholder = "Find a page, record type, menu, automation or past run…",
}: CommandPaletteProps) {
  const [focusId, setFocusId] = React.useState<string>("");
  const [actionsFor, setActionsFor] = React.useState<CommandItem | null>(null);
  const [search, setSearch] = React.useState("");
  React.useEffect(() => {
    if (!open) {
      setActionsFor(null);
      setSearch("");
    }
  }, [open]);
  if (!open) return null;

  const close = () => onOpenChange(false);
  const egg = search.trim().toLowerCase() === "ingenium"; // 149
  const base = [...items, ...dynamicItems];
  const allItems: CommandItem[] = actionsFor
    ? (actionsFor.actions ?? []).map((a) => ({ ...a, group: `Actions for ${actionsFor.label}` }))
    : egg
      ? [{ id: "egg-colophon", label: "Ingenium — the keystone story and credits", group: "Ingenium", onSelect: () => (window.location.href = "/colophon") }, ...base]
      : base;
  const focused = allItems.find((i) => `${i.label} ${i.keywords?.join(" ") ?? ""}`.toLowerCase() === focusId) ?? null;
  const groups = allItems.reduce<Record<string, CommandItem[]>>((acc, item) => {
    acc[item.group] = acc[item.group] ?? [];
    acc[item.group].push(item);
    return acc;
  }, {});

  return (
    <div className="fixed inset-0 z-[80]">
      <button
        type="button"
        className="absolute inset-0 bg-black/30 overlay-dim"
        aria-label="Close command palette"
        onClick={close}
      />
      <div className="absolute left-1/2 top-[12vh] w-full max-w-xl -translate-x-1/2 px-4">
        <Command
          className="overflow-hidden rounded-lg border border-border-subtle bg-surface-raised shadow-overlay"
          data-testid="command-palette"
          value={focusId}
          onValueChange={setFocusId}
          onKeyDown={(e) => {
            if ((e.key === "Tab" || ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k")) && focused?.actions?.length) {
              e.preventDefault();
              e.stopPropagation();
              setActionsFor(focused);
            } else if ((e.key === "Escape" || (e.key === "Backspace" && !search)) && actionsFor) {
              e.preventDefault();
              e.stopPropagation();
              setActionsFor(null); // 87: Esc steps back one level
            }
          }}
        >
          <div className="flex items-center gap-2 border-b border-border-subtle px-3">
            <Search className="h-4 w-4 text-muted" />
            <Command.Input
              placeholder={actionsFor ? `Actions for ${actionsFor.label}…` : placeholder}
              value={search}
              onValueChange={(v) => {
                setSearch(v);
                onSearchChange?.(v);
              }}
              className="h-11 w-full bg-transparent text-sm outline-none"
              autoFocus
            />
          </div>
          <div className="flex">
          <Command.List className="max-h-80 min-w-0 flex-1 overflow-auto p-2">
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
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate">{item.label}</span>
                      {item.actions?.length ? <kbd className="keycap">Tab</kbd> : null}
                    </span>
                  </Command.Item>
                ))}
              </Command.Group>
            ))}
          </Command.List>
          {focused && (focused.detail || focused.actions?.length) ? (
            <aside className="hidden w-56 shrink-0 border-l border-border-subtle p-3 text-sm sm:block" data-testid="command-preview">
              <p className="font-medium text-ink">{focused.label}</p>
              {focused.detail ? <p className="mt-1 text-muted">{focused.detail}</p> : null}
              {focused.actions?.length ? (
                <p className="mt-3 text-xs text-muted">Press Tab for {focused.actions.length} actions.</p>
              ) : null}
            </aside>
          ) : null}
          </div>
        </Command>
      </div>
    </div>
  );
}
