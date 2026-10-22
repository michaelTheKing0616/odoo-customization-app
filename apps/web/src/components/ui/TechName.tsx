"use client";

import * as React from "react";
import { cn } from "@/lib/cn";

/** Quiet mono chip for an Odoo technical name, one-click copy (design touch 13). */
export function TechName({ name, className }: { name: string; className?: string }) {
  const [copied, setCopied] = React.useState(false);
  return (
    <button
      type="button"
      className={cn(
        copied && "copied-glow",
        "tech-name inline-flex items-center rounded px-1 text-[0.85em] text-muted hover:text-ink focus-visible:outline-2",
        className,
      )}
      onClick={() => {
        void navigator.clipboard?.writeText(name).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1200);
        });
      }}
      aria-label={copied ? `Copied ${name}` : `Copy ${name}`}
      title={copied ? "Copied" : "Copy"}
    >
      {name}
    </button>
  );
}
