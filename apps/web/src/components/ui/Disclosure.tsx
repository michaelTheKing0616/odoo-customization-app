"use client";

import { ChevronDown } from "@/components/ui/icons";
import { cn } from "@/lib/cn";
import { useState, type ReactNode } from "react";

type Props = {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
  testId?: string;
  /** Sticky section head for dense inspectors (UI DESIGN BOT). */
  sticky?: boolean;
};

/** Collapsible section for advanced or secondary controls (UIF-4). */
export function Disclosure({
  title,
  children,
  defaultOpen = false,
  className,
  testId,
  sticky = false,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div
      className={cn("rounded-md border border-border-subtle bg-surface", className)}
      data-testid={testId}
    >
      <button
        type="button"
        className={cn(
          "flex w-full items-center justify-between gap-2 px-3 py-2 text-ui-label text-ink",
          sticky && "sticky top-0 z-[1] bg-surface",
        )}
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {title}
        <ChevronDown className={cn("h-4 w-4 shrink-0 transition-transform", open && "rotate-180")} />
      </button>
      {open ? (
        <div className="space-y-3 border-t border-border-subtle px-3 py-3">{children}</div>
      ) : null}
    </div>
  );
}
