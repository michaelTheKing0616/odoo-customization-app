import type { ReactNode } from "react";
import { Spokes } from "@/components/loading-ui/spokes";
import { cn } from "@/lib/cn";

type StudioBusyLabelProps = {
  children: ReactNode;
  className?: string;
};

export function StudioBusyLabel({ children, className }: StudioBusyLabelProps) {
  return (
    <span className={cn("studio-btn-busy", className)}>
      <Spokes className="studio-loader-spokes" aria-hidden />
      <span>{children}</span>
    </span>
  );
}

export function InlineWait({
  children = "Loading…",
  className,
}: {
  children?: ReactNode;
  className?: string;
}) {
  return (
    <p className={cn("studio-btn-busy mt-2 text-xs text-muted", className)}>
      <Spokes className="studio-loader-spokes" aria-hidden />
      <span>{children}</span>
    </p>
  );
}
