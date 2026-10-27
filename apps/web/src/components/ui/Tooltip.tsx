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

type TooltipOpenDetails = {
  reason: string;
  cancel: () => void;
};

export function Tooltip({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(false);
  const [handle] = React.useState(() => TooltipPrimitive.createHandle());
  const popupId = React.useId();
  const reduced = usePrefersReducedMotion();
  const triggerRef = React.useRef<HTMLElement | null>(null);
  const focusTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const keyboardOpenRef = React.useRef(false);

  const clearFocusTimer = React.useCallback(() => {
    if (focusTimerRef.current != null) {
      clearTimeout(focusTimerRef.current);
      focusTimerRef.current = null;
    }
  }, []);

  React.useEffect(() => clearFocusTimer, [clearFocusTimer]);

  // Hover already waits TOOLTIP_OPEN_DELAY_MS via the provider. Focus opens
  // immediately in Base UI, so hold it for the same 125–200 ms window.
  const armFocusOpen = React.useCallback(() => {
    clearFocusTimer();
    focusTimerRef.current = setTimeout(() => {
      focusTimerRef.current = null;
      const node = triggerRef.current;
      if (!node || document.activeElement !== node || node.id === "") return;
      keyboardOpenRef.current = true;
      handle.open(node.id);
    }, TOOLTIP_OPEN_DELAY_MS);
  }, [clearFocusTimer, handle]);

  const onOpenChange = React.useCallback(
    (next: boolean, details: TooltipOpenDetails) => {
      if (next && details.reason === "trigger-focus") {
        details.cancel();
        armFocusOpen();
        return;
      }
      if (details.reason === "trigger-hover") keyboardOpenRef.current = false;
      if (!next) clearFocusTimer();
      setOpen(next);
    },
    [armFocusOpen, clearFocusTimer],
  );

  const element = React.isValidElement<{ "aria-describedby"?: string }>(children) ? (
    children
  ) : (
    <button type="button">{children}</button>
  );
  const describedBy =
    [element.props["aria-describedby"], open ? popupId : undefined].filter(Boolean).join(" ") || undefined;
  const trigger = React.cloneElement(element, { "aria-describedby": describedBy });

  return (
    <TooltipPrimitive.Root handle={handle} onOpenChange={onOpenChange}>
      <TooltipPrimitive.Trigger
        ref={(node: HTMLButtonElement | null) => {
          triggerRef.current = node;
        }}
        handle={handle}
        onKeyDown={(event) => {
          if (event.key === "Escape") clearFocusTimer();
        }}
        render={trigger}
      />
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Positioner sideOffset={4}>
          <TooltipPrimitive.Popup
            id={popupId}
            role="tooltip"
            className={cn(
              "z-50 rounded-md border border-border-subtle bg-surface-overlay px-2 py-1 text-xs text-ink shadow-raised",
            )}
            style={(state) =>
              tooltipMotionStyle(
                keyboardOpenRef.current ? { ...state, instant: state.instant ?? "focus" } : state,
                reduced,
              )
            }
          >
            {label}
          </TooltipPrimitive.Popup>
        </TooltipPrimitive.Positioner>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
