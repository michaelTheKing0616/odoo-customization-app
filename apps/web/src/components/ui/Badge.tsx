import { cn } from "@/lib/cn";

type BadgeProps = {
  variant?: "default" | "success" | "warning" | "danger" | "info" | "lock" | "ga" | "experimental";
  children: React.ReactNode;
  className?: string;
};

const styles: Record<NonNullable<BadgeProps["variant"]>, string> = {
  default: "bg-surface-muted text-ink border-border-subtle",
  success: "bg-success-subtle text-success border-success/20",
  warning: "bg-warning-subtle text-warning border-warning/20",
  danger: "bg-danger-subtle text-danger border-danger/20",
  info: "bg-info-subtle text-info border-info/20",
  lock: "bg-warning-subtle text-warning border-warning/30",
  ga: "bg-success-subtle text-success border-success/20",
  experimental: "bg-warning-subtle text-warning border-warning/20",
};

export function Badge({ variant = "default", children, className }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
        styles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
