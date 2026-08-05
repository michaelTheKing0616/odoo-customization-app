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
};

/** Collapsible section for advanced or secondary controls (UIF-4). */
export function Disclosure({
  title,
  children,
  defaultOpen = false,
  className,
  testId,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={cn("rounded-md border border-border-subtle", className)} data-testid={testId}>
      <button
        type="button"
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-sm font-medium text-ink"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        {title}
        <ChevronDown className={cn("h-4 w-4 shrink-0 transition-transform", open && "rotate-180")} />
      </button>
      {open ? <div className="border-t border-border-subtle px-3 py-3">{children}</div> : null}
    </div>
  );
}
