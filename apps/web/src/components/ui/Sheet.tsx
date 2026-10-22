"use client";

import { useEffect, useRef } from "react";
import { Dialog } from "@base-ui/react/dialog";
import { X } from "@/components/ui/icons";
import { cn } from "@/lib/cn";
import { useFlickDismiss } from "@/components/ui/useFlickDismiss";

type SheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  /** Replaces the default title/description block. Title stays available to screen readers. */
  header?: React.ReactNode;
  side?: "right" | "left";
  children: React.ReactNode;
  className?: string;
  testId?: string;
};

function useReturnFocusOnClose(open: boolean) {
  const previousFocusRef = useRef<HTMLElement | null>(null);
  if (open && previousFocusRef.current == null && typeof document !== "undefined") {
    const active = document.activeElement;
    if (active instanceof HTMLElement) {
      previousFocusRef.current = active;
    }
  }
  useEffect(() => {
    if (open) return;
    const node = previousFocusRef.current;
    previousFocusRef.current = null;
    node?.focus?.();
  }, [open]);
  return previousFocusRef;
}

export function Sheet({
  open,
  onOpenChange,
  title,
  description,
  header,
  side = "right",
  children,
  className,
  testId,
}: SheetProps) {
  const previousFocusRef = useReturnFocusOnClose(open);
  const flick = useFlickDismiss(side, () => onOpenChange(false));
  return (
    <Dialog.Root open={open} onOpenChange={(nextOpen) => onOpenChange(nextOpen)}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-40 bg-black/30 backdrop-saturate-50 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=closed]:animate-out" />
        <Dialog.Popup
          data-testid={testId}
          ref={flick.panel}
          onWheel={flick.onWheel}
          finalFocus={previousFocusRef}
          className={cn(
            "fixed top-0 z-50 flex h-full w-full max-w-md flex-col border-border-subtle bg-surface-raised shadow-overlay outline-none",
            side === "right" ? "right-0 border-l" : "left-0 border-r",
            className,
          )}
        >
          <div {...flick.handle} className="flex cursor-grab items-start justify-between gap-3 border-b border-border-subtle px-4 py-3 active:cursor-grabbing">
            <div className="min-w-0 flex-1">
              {header ? (
                <>
                  {title ? <Dialog.Title className="sr-only">{title}</Dialog.Title> : null}
                  {description ? (
                    <Dialog.Description className="sr-only">{description}</Dialog.Description>
                  ) : null}
                  {header}
                </>
              ) : (
                <>
                  {title ? (
                    <Dialog.Title className="text-md font-semibold text-ink">{title}</Dialog.Title>
                  ) : null}
                  {description ? (
                    <Dialog.Description className="mt-1 text-sm text-muted">
                      {description}
                    </Dialog.Description>
                  ) : null}
                </>
              )}
            </div>
            <Dialog.Close
              className="rounded-md p-1 text-muted hover:bg-surface-muted"
              aria-label="Close panel"
            >
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
