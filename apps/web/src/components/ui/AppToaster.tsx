"use client";

import { useEffect } from "react";
import { Toaster, toast } from "sonner";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";

/** Success/info use Toaster default duration (4000 ms). Errors persist until dismissed. */
export const APP_TOAST_DURATION_MS = 4000;

function ApiErrorToastListener() {
  useEffect(() => {
    const handler = (event: Event) => {
      const { message } = (event as CustomEvent<{ message: string }>).detail;
      toast.error("Request failed", {
        description: message,
        action: {
          label: "Diagnose with Expert",
          onClick: () => diagnoseWithExpert(message),
        },
      });
    };
    window.addEventListener("app:api-error", handler);
    return () => window.removeEventListener("app:api-error", handler);
  }, []);
  return null;
}

function useSonnerErrorDefaults() {
  useEffect(() => {
    const baseError = toast.error.bind(toast);
    toast.error = (message, data) =>
      baseError(message, { duration: Infinity, ...data });
    return () => {
      toast.error = baseError;
    };
  }, []);
}

export function AppToaster() {
  useSonnerErrorDefaults();

  return (
    <>
      <ApiErrorToastListener />
      <Toaster
        duration={APP_TOAST_DURATION_MS}
        richColors={false}
        closeButton
        toastOptions={{
          classNames: {
            toast: "bg-surface border border-border text-ink",
          },
        }}
      />
    </>
  );
}
