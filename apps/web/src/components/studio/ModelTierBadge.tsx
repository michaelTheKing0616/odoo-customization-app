"use client";

import { Badge } from "@/components/ui/Badge";

type ModelTierBadgeProps = {
  provider?: string | null;
  fallbackUsed?: boolean;
};

export function ModelTierBadge({ provider, fallbackUsed }: ModelTierBadgeProps) {
  const name = (provider || "off").toLowerCase();
  const local = name === "ollama";
  const label = local ? "Running locally" : fallbackUsed ? "Cloud · fallback" : "Cloud";
  return (
    <span className="model-badge" data-testid="studio-model-tier">
      <Badge variant={local ? "success" : "info"}>
        {label}
        {name !== "off" && !local ? ` (${name})` : null}
      </Badge>
    </span>
  );
}
