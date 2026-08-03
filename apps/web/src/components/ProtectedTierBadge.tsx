"use client";

import type { ProtectedTier } from "@/lib/api";

const COPY: Record<
  ProtectedTier,
  { label: string; icon: string; title: string; className: string }
> = {
  tier_1: {
    label: "Tier 1",
    icon: "🔒",
    title:
      "Tier 1 (lock): never generate write/automation logic against this model. " +
      "Link from custom (x_*) models via many2one/one2many only. Chatter/activity allowed.",
    className: "border-amber-700/60 bg-amber-950/40 text-amber-200",
  },
  tier_2: {
    label: "Tier 2",
    icon: "🛡️",
    title:
      "Tier 2 (shield): extend via additive custom (x_*) fields only. " +
      "Do not delete or rename stock fields; do not replace core behaviour.",
    className: "border-sky-800/60 bg-sky-950/40 text-sky-200",
  },
};

export function ProtectedTierBadge({
  tier,
  className = "",
}: {
  tier: ProtectedTier | null | undefined;
  className?: string;
}) {
  if (!tier) return null;
  const meta = COPY[tier];
  return (
    <span
      title={meta.title}
      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${meta.className} ${className}`}
    >
      <span aria-hidden>{meta.icon}</span>
      {meta.label}
    </span>
  );
}
