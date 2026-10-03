"use client";

import { Toaster } from "sonner";

export function AppToaster() {
  return (
    <Toaster
      duration={4000}
      richColors={false}
      closeButton
      toastOptions={{
        classNames: {
          toast: "bg-surface border border-border text-ink",
        },
      }}
    />
  );
}
