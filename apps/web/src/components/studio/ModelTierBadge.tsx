"use client";

type ModelTierBadgeProps = {
  provider?: string | null;
  fallbackUsed?: boolean;
};

export function ModelTierBadge({ provider, fallbackUsed }: ModelTierBadgeProps) {
  const name = (provider || "off").toLowerCase();
  const local = name === "ollama";
  const label = local ? "Running locally" : fallbackUsed ? "Cloud · fallback" : "Cloud";
  return (
    <span className="model-badge">
      {local ? <span aria-hidden>⬡</span> : null}
      {label}
      {name !== "off" && !local ? ` (${name})` : null}
    </span>
  );
}
