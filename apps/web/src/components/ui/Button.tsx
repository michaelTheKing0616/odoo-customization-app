"use client";

import { useRender } from "@base-ui/react/use-render";
import { Children, createElement, isValidElement } from "react";
import { Spokes } from "@/components/loading-ui/spokes";
import { cn } from "@/lib/cn";

/** One primary action per screen — use variant="primary" sparingly. */
export type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  loading?: boolean;
  /** Render the single child element (e.g. a Link) with the button's classes and props. */
  asChild?: boolean;
  ref?: React.Ref<HTMLElement>;
};

type ChildProps = Record<string, unknown>;

const disabledAsChildClassName =
  "aria-disabled:opacity-50 aria-disabled:pointer-events-none";

const interactionPropKeys = [
  "onClick",
  "onPointerDown",
  "onMouseDown",
  "onKeyDown",
  "onKeyUp",
  "tabIndex",
] as const;

function omitInteraction<T extends object>(props: T): T {
  const rest = { ...props } as Record<string, unknown>;
  for (const key of interactionPropKeys) delete rest[key];
  return rest as T;
}

/**
 * Child handlers run before the Button's in Base UI's mergeProps, so a disabled
 * asChild target must have them removed rather than intercepted.
 */
function withoutInteraction(child: React.ReactElement<ChildProps>) {
  return createElement(child.type, { ...omitInteraction(child.props), key: child.key });
}

function preventActivation(event: React.SyntheticEvent) {
  event.preventDefault();
}

function SlotButton({
  child,
  className,
  isDisabled,
  ref,
  props,
}: {
  child: React.ReactElement<ChildProps>;
  className: string;
  isDisabled: boolean;
  ref?: React.Ref<HTMLElement>;
  props: Omit<ButtonProps, "asChild" | "variant" | "size" | "loading" | "disabled" | "ref">;
}) {
  return useRender({
    render: isDisabled ? withoutInteraction(child) : child,
    ref,
    props: isDisabled
      ? {
          ...omitInteraction(props),
          className: cn(className, disabledAsChildClassName),
          "aria-disabled": true,
          "data-disabled": "",
          tabIndex: -1,
          onClick: preventActivation,
        }
      : { ...props, className },
  });
}

const variants = {
  primary:
    "bg-accent text-on-accent hover:bg-accent-hover border border-transparent shadow-subtle",
  secondary:
    "bg-surface-raised text-ink border border-border-subtle hover:bg-surface-muted",
  ghost: "bg-transparent text-ink hover:bg-surface-muted border border-transparent",
  danger:
    "bg-danger text-on-danger hover:bg-danger-strong border border-transparent",
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
  ref,
  ...props
}: ButtonProps) {
  const sharedClassName = cn(
    "inline-flex items-center justify-center rounded-md font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none",
    variants[variant],
    sizes[size],
    className,
  );

  if (asChild) {
    // Children.only rejects a string before Button can name that case.
    if (!isValidElement(children) && Children.count(children) === 1) {
      const [onlyChild] = Children.toArray(children);
      if (!isValidElement(onlyChild)) {
        throw new Error("Button: asChild expects a single React element child.");
      }
    }
    const child = Children.only(children);
    if (!isValidElement(child)) {
      throw new Error("Button: asChild expects a single React element child.");
    }
    return (
      <SlotButton
        child={child as React.ReactElement<ChildProps>}
        className={sharedClassName}
        isDisabled={Boolean(disabled || loading)}
        ref={ref}
        props={props}
      />
    );
  }

  return (
    <button
      ref={ref as React.Ref<HTMLButtonElement>}
      className={sharedClassName}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Spokes className="studio-loader-spokes h-4 w-4" aria-hidden /> : null}
      {children}
    </button>
  );
}
