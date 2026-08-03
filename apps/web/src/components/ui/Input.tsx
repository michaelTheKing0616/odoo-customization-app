"use client";

import { cn } from "@/lib/cn";

export type InputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label?: string;
  hint?: string;
  error?: string;
};

export function Input({ label, hint, error, className, id, ...props }: InputProps) {
  const inputId = id ?? (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);
  return (
    <div className="space-y-1.5">
      {label ? (
        <label htmlFor={inputId} className="block text-sm font-medium text-ink">
          {label}
        </label>
      ) : null}
      <input
        id={inputId}
        className={cn(
          "h-9 w-full rounded-md border border-border-subtle bg-surface px-3 text-sm text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2",
          error && "border-danger/50",
          className,
        )}
        {...props}
      />
      {hint && !error ? <p className="text-xs text-muted">{hint}</p> : null}
      {error ? <p className="text-xs text-danger">{error}</p> : null}
    </div>
  );
}
