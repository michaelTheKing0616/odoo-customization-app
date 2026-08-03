"use client";

import { Slot } from "@radix-ui/react-slot";
import { Loader2 } from "@/components/ui/icons";
import { cn } from "@/lib/cn";

/** One primary action per screen — use variant="primary" sparingly. */
export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
  asChild?: boolean;
};

const variants = {
  primary:
    "bg-accent text-on-accent hover:bg-accent-hover border border-transparent shadow-subtle",
  secondary:
    "bg-surface-raised text-ink border border-border-subtle hover:bg-surface-muted",
  ghost: "bg-transparent text-ink hover:bg-surface-muted border border-transparent",
  danger:
    "bg-danger text-white hover:bg-danger-strong border border-transparent",
};

const sizes = {
  sm: "h-8 px-3 text-sm gap-1.5",
  md: "h-9 px-4 text-sm gap-2",
};

export function Button({
  className,
  variant = "secondary",
  size = "md",
  loading,
  disabled,
  asChild,
  children,
  ...props
}: ButtonProps) {
  const Comp = asChild ? Slot : "button";
  return (
    <Comp
      className={cn(
        "inline-flex items-center justify-center rounded-md font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none",
        variants[variant],
        sizes[size],
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
      {children}
    </Comp>
  );
}
