"use client";

import { Command } from "cmdk";
import { useMemo, useState } from "react";
import { cn } from "@/lib/cn";

export type ComboboxOption = { value: string; label: string; keywords?: string[] };

type ComboboxProps = {
  options: ComboboxOption[];
  value?: string;
  onValueChange: (value: string) => void;
  placeholder?: string;
  emptyLabel?: string;
  className?: string;
  loading?: boolean;
};

export function Combobox({
  options,
  value,
  onValueChange,
  placeholder = "Search…",
  emptyLabel = "No matches",
  className,
  loading,
}: ComboboxProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const selected = options.find((o) => o.value === value);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return options;
    return options.filter(
      (o) =>
        o.label.toLowerCase().includes(q) ||
        o.value.toLowerCase().includes(q) ||
        o.keywords?.some((k) => k.toLowerCase().includes(q)),
    );
  }, [options, query]);

  return (
    <div className={cn("relative", className)}>
      <button
        type="button"
        className="flex h-9 w-full items-center justify-between rounded-md border border-border-subtle bg-surface px-3 text-left text-sm"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        data-testid="combobox-trigger"
      >
        <span className={selected ? "text-ink" : "text-muted"}>
          {selected?.label ?? placeholder}
        </span>
        <span className="text-muted" aria-hidden>
          ▾
        </span>
      </button>
      {open ? (
        <div className="absolute z-20 mt-1 w-full overflow-hidden rounded-md border border-border-subtle bg-surface-raised shadow-overlay">
          <Command shouldFilter={false}>
            <Command.Input
              value={query}
              onValueChange={setQuery}
              placeholder={placeholder}
              className="h-9 w-full border-b border-border-subtle bg-transparent px-3 text-sm outline-none"
            />
            <Command.List className="max-h-48 overflow-auto p-1">
              {loading ? (
                <div className="px-3 py-2 text-sm text-muted">Loading…</div>
              ) : null}
              {!loading && filtered.length === 0 ? (
                <div className="px-3 py-2 text-sm text-muted">{emptyLabel}</div>
              ) : null}
              {filtered.map((opt) => (
                <Command.Item
                  key={opt.value}
                  value={opt.value}
                  onSelect={() => {
                    onValueChange(opt.value);
                    setOpen(false);
                    setQuery("");
                  }}
                  className="cursor-pointer rounded-md px-2 py-1.5 text-sm aria-selected:bg-accent-subtle"
                >
                  {opt.label}
                </Command.Item>
              ))}
            </Command.List>
          </Command>
        </div>
      ) : null}
    </div>
  );
}
