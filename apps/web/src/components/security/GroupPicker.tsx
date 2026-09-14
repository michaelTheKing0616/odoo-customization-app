"use client";

import { useState } from "react";
import type { GroupRow } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";

type GroupPickerProps = {
  groups: GroupRow[];
  value: number[];
  onChange: (ids: number[]) => void;
  multiple?: boolean;
  label?: string;
  hint?: string;
  noneLabel?: string;
  testId?: string;
};

export function GroupPicker({
  groups,
  value,
  onChange,
  multiple = true,
  label = "Groups",
  hint,
  noneLabel = "All users",
  testId = "group-picker",
}: GroupPickerProps) {
  const [query, setQuery] = useState("");
  const needle = query.trim().toLowerCase();
  const filtered = groups.filter((g) => {
    if (!needle) return true;
    return `${g.name} ${g.full_name ?? ""}`.toLowerCase().includes(needle);
  });
  const selected = groups.filter((g) => value.includes(g.id));

  function toggle(id: number) {
    if (multiple) {
      onChange(value.includes(id) ? value.filter((x) => x !== id) : [...value, id]);
      return;
    }
    onChange(value.includes(id) ? [] : [id]);
  }

  return (
    <div className="space-y-2" data-testid={testId}>
      <div>
        <p className="text-sm font-medium text-ink">{label}</p>
        {hint ? <p className="mt-0.5 text-xs text-muted">{hint}</p> : null}
      </div>
      {selected.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {selected.map((g) => (
            <Badge key={g.id} variant="info">
              {g.full_name || g.name}
            </Badge>
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted">{noneLabel}</p>
      )}
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Filter groups"
        aria-label="Filter groups"
        className="h-9 w-full rounded-md border border-border-subtle bg-surface px-3 text-sm text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2"
      />
      <ul className="max-h-40 space-y-1 overflow-auto rounded-md border border-border-subtle bg-surface p-1">
        {filtered.length === 0 ? (
          <li className="px-2 py-1.5 text-xs text-muted">No matching groups</li>
        ) : (
          filtered.slice(0, 80).map((g) => {
            const checked = value.includes(g.id);
            return (
              <li key={g.id}>
                <label
                  className={cn(
                    "flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-surface-muted",
                    checked && "bg-accent-subtle",
                  )}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(g.id)}
                  />
                  <span className="min-w-0 truncate text-ink">{g.full_name || g.name}</span>
                </label>
              </li>
            );
          })
        )}
      </ul>
    </div>
  );
}
