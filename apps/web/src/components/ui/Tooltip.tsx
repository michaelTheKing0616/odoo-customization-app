"use client";

import * as React from "react";
import { Tooltip as TooltipPrimitive } from "@base-ui/react/tooltip";
import { cn } from "@/lib/cn";
import {
  DURATION,
  EASE_ENTER_EXIT,
  MOTION_PROPERTIES,
  PRESS_SCALE,
  exitDurationMs,
} from "@/components/ui/motion/constants";
import { usePrefersReducedMotion } from "@/components/ui/motion/usePrefersReducedMotion";

export const TOOLTIP_OPEN_DELAY_MS = 200;

type TooltipMotionState = Pick<TooltipPrimitive.Popup.State, "open" | "instant" | "transitionStatus">;

/** Popup style per state. Reduced motion drops the transform and keeps opacity only. */
export function tooltipMotionStyle(state: TooltipMotionState, reduced: boolean): React.CSSProperties {
  const hidden = state.transitionStatus === "starting" || state.transitionStatus === "ending";
  const enterMs = DURATION.dropdownMs;
  const durationMs = state.instant
    ? 0
    : reduced
      ? DURATION.reducedMotionMs
      : state.open
        ? enterMs
        : exitDurationMs(enterMs);
  const properties = reduced ? ["opacity"] : MOTION_PROPERTIES;
  return {
    opacity: hidden ? 0 : 1,
    transform: reduced ? undefined : hidden ? `scale(${PRESS_SCALE})` : "scale(1)",
    transformOrigin: "var(--transform-origin)",
    transition: properties.map((property) => `${property} ${durationMs}ms ${EASE_ENTER_EXIT.css}`).join(", "),
  };
}

export function TooltipProvider({ children }: { children: React.ReactNode }) {
  return <TooltipPrimitive.Provider delay={TOOLTIP_OPEN_DELAY_MS}>{children}</TooltipPrimitive.Provider>;
}

export function Tooltip({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(false);
  const popupId = React.useId();
  const reduced = usePrefersReducedMotion();

  const element = React.isValidElement<{ "aria-describedby"?: string }>(children) ? (
    children
  ) : (
    <button type="button">{children}</button>
  );
  const describedBy =
    [element.props["aria-describedby"], open ? popupId : undefined].filter(Boolean).join(" ") || undefined;
  const trigger = React.cloneElement(element, { "aria-describedby": describedBy });

  return (
    <TooltipPrimitive.Root onOpenChange={setOpen}>
      <TooltipPrimitive.Trigger render={trigger} />
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Positioner sideOffset={4}>
          <TooltipPrimitive.Popup
            id={popupId}
            role="tooltip"
            className={cn(
              "z-50 rounded-md border border-border-subtle bg-surface-overlay px-2 py-1 text-xs text-ink shadow-raised",
            )}
            style={(state) => tooltipMotionStyle(state, reduced)}
          >
            {label}
          </TooltipPrimitive.Popup>
        </TooltipPrimitive.Positioner>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
