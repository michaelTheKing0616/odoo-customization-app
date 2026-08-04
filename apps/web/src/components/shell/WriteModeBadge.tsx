"use client";

import type { Connection } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";

const LABELS: Record<string, string> = {
  observer: "Observer",
  standard: "Standard",
  production: "Production",
};

export function WriteModeBadge({ mode }: { mode: Connection["write_mode"] }) {
  const label = LABELS[mode] ?? mode;
  if (mode === "production") {
    return <Badge variant="warning">{label}</Badge>;
  }
  if (mode === "observer") {
    return <Badge>{label}</Badge>;
  }
  return <Badge variant="ga">{label}</Badge>;
}
