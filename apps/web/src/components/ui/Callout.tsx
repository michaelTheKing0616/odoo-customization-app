import { AlertTriangle, CircleAlert, Info } from "@/components/ui/icons";
import { cn } from "@/lib/cn";

type CalloutProps = {
  variant?: "info" | "warning" | "danger";
  title: string;
  children?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
  testId?: string;
};

const icons = {
  info: Info,
  warning: AlertTriangle,
  danger: CircleAlert,
};

const styles = {
  info: "border-info/30 bg-info-subtle text-ink",
  warning: "border-warning/30 bg-warning-subtle text-ink",
  danger: "border-danger/30 bg-danger-subtle text-ink",
};

export function Callout({
  variant = "info",
  title,
  children,
  actions,
  className,
  testId,
}: CalloutProps) {
  const Icon = icons[variant];
  return (
    <div
      className={cn("rounded-md border p-4 text-sm", styles[variant], className)}
      data-testid={testId}
      role="status"
    >
      <div className="flex gap-2">
        <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-medium" data-testid={testId === "gating-callout" ? "gating-title" : undefined}>
            {title}
          </p>
          {children ? <div className="mt-2 text-muted">{children}</div> : null}
          {actions ? <div className="mt-3 flex flex-wrap gap-2">{actions}</div> : null}
        </div>
      </div>
    </div>
  );
}
