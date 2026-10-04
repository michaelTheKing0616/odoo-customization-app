"use client";

import { useEffect, useRef } from "react";
import { Dialog } from "@base-ui/react/dialog";
import { X } from "@/components/ui/icons";
import { cn } from "@/lib/cn";

type DialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
  testId?: string;
  dataRiskLevel?: string;
  headerClassName?: string;
  headerTestId?: string;
  titleClassName?: string;
  initialFocus?: React.ComponentProps<typeof Dialog.Popup>["initialFocus"];
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

export function DialogPanel({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  className,
  testId,
  dataRiskLevel,
  headerClassName,
  headerTestId,
  titleClassName,
  initialFocus,
}: DialogProps) {
  const previousFocusRef = useReturnFocusOnClose(open);
  const callerSetsBorderColor = className
    ?.split(/\s+/)
    .some((token) => token.startsWith("border-"));
  return (
    <Dialog.Root open={open} onOpenChange={(nextOpen) => onOpenChange(nextOpen)}>
      <Dialog.Portal>
        <Dialog.Backdrop className="fixed inset-0 z-50 bg-black/40" />
        <Dialog.Popup
          data-testid={testId ?? "dialog-panel"}
          data-risk-level={dataRiskLevel}
          finalFocus={previousFocusRef}
          initialFocus={initialFocus}
          className={cn(
            "fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-lg border bg-surface-raised p-5 shadow-overlay outline-none",
            callerSetsBorderColor ? className : cn("border-border-subtle", className),
          )}
        >
          <div
            className={cn("flex items-start justify-between gap-3", headerClassName)}
            data-testid={headerTestId}
          >
            <div>
              <Dialog.Title
                className={
                  titleClassName
                    ? cn("font-semibold", titleClassName)
                    : "text-md font-semibold text-ink"
                }
              >
                {title}
              </Dialog.Title>
              {description ? (
                <Dialog.Description className="mt-1 text-sm text-muted">
                  {description}
                </Dialog.Description>
              ) : null}
            </div>
            <Dialog.Close
              className="rounded-md p-1 text-muted hover:bg-surface-muted"
              aria-label="Close dialog"
            >
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>
          <div className="mt-4">{children}</div>
          {footer ? <div className="mt-4 flex justify-end gap-2">{footer}</div> : null}
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
