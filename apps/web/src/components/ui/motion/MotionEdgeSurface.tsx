"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { motion } from "motion/react";
import { X } from "@/components/ui/icons";
import { cn } from "@/lib/cn";
import type { MotionSide } from "./resolve";
import {
  DRAWER_INTERRUPTIBLE,
  backdropAnimate,
  motionKeys,
  panelTransition,
  resolvePanelAnimate,
} from "./resolve";
import { usePrefersReducedMotion } from "./usePrefersReducedMotion";

export type MotionEdgeSurfaceProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  side?: MotionSide;
  children: ReactNode;
  className?: string;
  testId?: string;
  closeLabel: string;
  panelTestId: string;
};

/**
 * Persistent edge panel. `animate` is the only driver (`initial` is not
 * re-applied on close), so a close mid-open reverses from the current value.
 */
export function MotionEdgeSurface({
  open,
  onOpenChange,
  title,
  description,
  side = "right",
  children,
  className,
  testId,
  closeLabel,
  panelTestId,
}: MotionEdgeSurfaceProps) {
  const reduced = usePrefersReducedMotion();
  const animate = resolvePanelAnimate(open, side, reduced);
  const transition = panelTransition(open, reduced);
  const panelRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onOpenChange(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onOpenChange]);

  return (
    <div
      data-testid={testId}
      data-interruptible={DRAWER_INTERRUPTIBLE.remountOnToggle ? "false" : "true"}
      inert={open ? undefined : true}
      className={cn("fixed inset-0 z-50", !open && "pointer-events-none")}
    >
      <motion.div
        aria-hidden
        className="absolute inset-0 bg-black/40"
        initial={false}
        animate={backdropAnimate(open)}
        transition={transition}
        onClick={() => onOpenChange(false)}
      />
      <motion.aside
        ref={panelRef}
        role="dialog"
        aria-modal={open}
        aria-hidden={!open}
        aria-label={title}
        data-testid={panelTestId}
        data-motion-keys={motionKeys(animate).sort().join(" ")}
        initial={false}
        animate={animate}
        transition={transition}
        onUpdate={(latest) => {
          const node = panelRef.current;
          if (!node || latest.x === undefined) return;
          node.dataset.motionX = String(latest.x);
        }}
        className={cn(
          "absolute top-0 z-50 flex h-full w-full max-w-md flex-col border-border-subtle bg-surface-raised shadow-overlay outline-none",
          side === "right" ? "right-0 border-l" : "left-0 border-r",
          className,
        )}
      >
        <div className="flex items-start justify-between gap-3 border-b border-border-subtle px-4 py-3">
          <div className="min-w-0 flex-1">
            {title ? <h2 className="text-md font-semibold text-ink">{title}</h2> : null}
            {description ? <p className="mt-1 text-sm text-muted">{description}</p> : null}
          </div>
          <button
            type="button"
            className="rounded-md p-1 text-muted hover:bg-surface-muted"
            aria-label={closeLabel}
            onClick={() => onOpenChange(false)}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
      </motion.aside>
    </div>
  );
}
