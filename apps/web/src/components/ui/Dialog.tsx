"use client";

import * as Dialog from "@radix-ui/react-dialog";
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
};

export function DialogPanel({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  className,
  testId,
}: DialogProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <Dialog.Content
          data-testid={testId ?? "dialog-panel"}
          className={cn(
            "fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-lg border border-border-subtle bg-surface-raised p-5 shadow-overlay outline-none",
            className,
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <div>
              <Dialog.Title className="text-md font-semibold text-ink">{title}</Dialog.Title>
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
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
