"use client";

import Link from "next/link";
import type { BuildSpineChip } from "@/lib/build-spine";

type BuildSpineChipsProps = {
  chips: BuildSpineChip[];
  connectionId: string;
  onSelect?: (chip: BuildSpineChip) => void;
};

export function BuildSpineChips({ chips, connectionId, onSelect }: BuildSpineChipsProps) {
  if (!chips.length) return null;
  return (
    <div
      className="flex flex-wrap gap-2"
      data-testid="build-spine-chips"
      data-connection-id={connectionId}
      role="tablist"
      aria-label="Build mode"
    >
      {chips.map((chip) => {
        const className = chip.active
          ? "rounded-full border border-accent bg-accent/10 px-3 py-1 text-xs font-medium text-accent"
          : "rounded-full border border-line bg-surface px-3 py-1 text-xs font-medium text-muted hover:border-accent hover:text-ink";
        if (onSelect) {
          return (
            <button
              key={chip.id}
              type="button"
              role="tab"
              aria-selected={chip.active}
              title={chip.blurb}
              className={className}
              data-testid={`build-spine-chip-${chip.id}`}
              data-active={chip.active ? "1" : "0"}
              onClick={() => onSelect(chip)}
            >
              {chip.label}
            </button>
          );
        }
        return (
          <Link
            key={chip.id}
            href={chip.href}
            role="tab"
            aria-selected={chip.active}
            title={chip.blurb}
            className={className}
            data-testid={`build-spine-chip-${chip.id}`}
            data-active={chip.active ? "1" : "0"}
          >
            {chip.label}
          </Link>
        );
      })}
    </div>
  );
}
