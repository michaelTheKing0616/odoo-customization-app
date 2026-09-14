"use client";

import { CRUD_KEYS, type CrudPermits } from "@/lib/accessForm";
import { cn } from "@/lib/cn";

type CrudPermitsControlProps = {
  value: CrudPermits;
  onChange: (patch: Partial<CrudPermits>) => void;
  disabled?: boolean;
};

export function CrudPermitsControl({ value, onChange, disabled }: CrudPermitsControlProps) {
  return (
    <div className="flex flex-wrap gap-2" data-testid="crud-permits">
      {CRUD_KEYS.map(([key, label]) => {
        const on = value[key];
        return (
          <label
            key={key}
            className={cn(
              "inline-flex cursor-pointer items-center gap-2 rounded-md border px-2.5 py-1.5 text-sm",
              on
                ? "border-accent bg-accent-subtle text-ink"
                : "border-border-subtle bg-surface text-muted",
              disabled && "cursor-not-allowed opacity-60",
            )}
          >
            <input
              type="checkbox"
              className="sr-only"
              checked={on}
              disabled={disabled}
              onChange={(e) => onChange({ [key]: e.target.checked })}
            />
            <span className="font-medium">{label}</span>
          </label>
        );
      })}
    </div>
  );
}
