import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/cn";

type StatusPillProps = {
  kind:
    | "ga"
    | "experimental"
    | "tier1-lock"
    | "tier2-shield"
    | "hosting-online"
    | "hosting-sh"
    | "hosting-onprem"
    | "internal";
  className?: string;
};

const labels: Record<StatusPillProps["kind"], string> = {
  ga: "GA",
  experimental: "Experimental",
  "tier1-lock": "Tier 1 lock",
  "tier2-shield": "Tier 2",
  "hosting-online": "Odoo Online",
  "hosting-sh": "Odoo.sh",
  "hosting-onprem": "On-prem",
  internal: "Internal",
};

const variants: Record<
  StatusPillProps["kind"],
  React.ComponentProps<typeof Badge>["variant"]
> = {
  ga: "ga",
  experimental: "experimental",
  "tier1-lock": "lock",
  "tier2-shield": "info",
  "hosting-online": "info",
  "hosting-sh": "info",
  "hosting-onprem": "default",
  internal: "warning",
};

export function StatusPill({ kind, className }: StatusPillProps) {
  return (
    <Badge variant={variants[kind]} className={cn(className)}>
      {labels[kind]}
    </Badge>
  );
}
