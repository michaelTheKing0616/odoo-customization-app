"use client";

import { cn } from "@/lib/cn";

export type SelectOption = { value: string; label: string; disabled?: boolean };

export type SelectProps = Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "children"> & {
  label?: string;
  hint?: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
};

export function Select({
  label,
  hint,
  error,
  options,
  placeholder,
  className,
  id,
  ...props
}: SelectProps) {
  const selectId = id ?? (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);
  return (
    <div className="space-y-1.5">
      {label ? (
        <label htmlFor={selectId} className="block text-sm font-medium text-ink">
          {label}
        </label>
      ) : null}
      <select
        id={selectId}
        className={cn(
          "h-9 w-full rounded-md border border-border-subtle bg-surface px-3 text-sm text-ink outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2",
          error && "border-danger/50",
          className,
        )}
        {...props}
      >
        {placeholder ? (
          <option value="" disabled>
            {placeholder}
          </option>
        ) : null}
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} disabled={opt.disabled}>
            {opt.label}
          </option>
        ))}
      </select>
      {hint && !error ? <p className="text-xs text-muted">{hint}</p> : null}
      {error ? <p className="text-xs text-danger">{error}</p> : null}
    </div>
  );
}
