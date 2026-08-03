"use client";

import { cn } from "@/lib/cn";

export type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: string;
  hint?: string;
  error?: string;
};

export function Textarea({ label, hint, error, className, id, ...props }: TextareaProps) {
  const inputId = id ?? (label ? label.toLowerCase().replace(/\s+/g, "-") : undefined);
  return (
    <div className="space-y-1.5">
      {label ? (
        <label htmlFor={inputId} className="block text-sm font-medium text-ink">
          {label}
        </label>
      ) : null}
      <textarea
        id={inputId}
        className={cn(
          "min-h-[88px] w-full rounded-md border border-border-subtle bg-surface px-3 py-2 text-sm text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2",
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
