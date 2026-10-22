"use client";

import { toast } from "sonner";
import { celebrateKeystone } from "@/components/brand/BrandMark";

/** Touch 70: success sized to the stakes. Small things get a check; a big first gets the
 * keystone landing and a summary of what changed, once per first. Returns "first" or "small". */
export function markSuccess(o: { title: string; firstKey?: string; summary?: string[] }): "first" | "small" {
  let first = false;
  if (o.firstKey) {
    try {
      const k = `ingenium.first.${o.firstKey}`;
      if (!localStorage.getItem(k)) {
        localStorage.setItem(k, new Date().toISOString());
        first = true;
      }
    } catch {
      first = false;
    }
  }
  if (!first) {
    toast.success(o.title);
    return "small";
  }
  celebrateKeystone();
  toast.success(o.title, {
    duration: 8000,
    description: o.summary?.length ? (
      <ul className="mt-1 list-disc pl-4 text-xs" data-testid="success-summary">
        {o.summary.map((line) => <li key={line}>{line}</li>)}
      </ul>
    ) : undefined,
  });
  return "first";
}
