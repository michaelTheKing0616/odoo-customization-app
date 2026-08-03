"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { X } from "@/components/ui/icons";
import { cn } from "@/lib/cn";

type SheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  side?: "right" | "left";
  children: React.ReactNode;
  className?: string;
  testId?: string;
};

export function Sheet({
  open,
  onOpenChange,
  title,
  description,
  side = "right",
  children,
  className,
  testId,
}: SheetProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/40 data-[state=open]:animate-in data-[state=closed]:animate-out" />
        <Dialog.Content
          data-testid={testId}
          className={cn(
            "fixed top-0 z-50 flex h-full w-full max-w-md flex-col border-border-subtle bg-surface-raised shadow-overlay outline-none",
            side === "right" ? "right-0 border-l" : "left-0 border-r",
            className,
          )}
        >
          <div className="flex items-start justify-between gap-3 border-b border-border-subtle px-4 py-3">
            <div>
              {title ? (
                <Dialog.Title className="text-md font-semibold text-ink">{title}</Dialog.Title>
              ) : null}
              {description ? (
                <Dialog.Description className="mt-1 text-sm text-muted">
                  {description}
                </Dialog.Description>
              ) : null}
            </div>
            <Dialog.Close
              className="rounded-md p-1 text-muted hover:bg-surface-muted"
              aria-label="Close panel"
            >
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
