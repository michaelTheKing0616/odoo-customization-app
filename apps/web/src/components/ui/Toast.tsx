"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { diagnoseWithExpert } from "@/lib/expert-diagnostics";
import { cn } from "@/lib/cn";

type ToastVariant = "success" | "error" | "info";

type ToastItem = {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
  action?: { label: string; onClick: () => void };
};

type ToastContextValue = {
  toast: (item: Omit<ToastItem, "id">) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

function ApiErrorToastListener({ toast }: { toast: ToastContextValue["toast"] }) {
  useEffect(() => {
    const handler = (event: Event) => {
      const { message } = (event as CustomEvent<{ message: string }>).detail;
      toast({
        variant: "error",
        title: "Request failed",
        description: message,
        action: {
          label: "Diagnose with Expert",
          onClick: () => diagnoseWithExpert(message),
        },
      });
    };
    window.addEventListener("app:api-error", handler);
    return () => window.removeEventListener("app:api-error", handler);
  }, [toast]);
  return null;
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);

  const toast = useCallback((item: Omit<ToastItem, "id">) => {
    const id = crypto.randomUUID();
    setItems((prev) => [...prev, { ...item, id }]);
    window.setTimeout(() => {
      setItems((prev) => prev.filter((t) => t.id !== id));
    }, 6000);
  }, []);

  const value = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={value}>
      <ApiErrorToastListener toast={toast} />
      {children}
      <div
        className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-full max-w-sm flex-col gap-2"
        aria-live="polite"
      >
        {items.map((item) => (
          <div
            key={item.id}
            className={cn(
              "pointer-events-auto rounded-md border px-4 py-3 shadow-raised",
              item.variant === "success" && "border-success/30 bg-success-subtle",
              item.variant === "error" && "border-danger/30 bg-danger-subtle",
              item.variant === "info" && "border-border-subtle bg-surface-raised",
            )}
            data-testid="toast"
          >
            <p className="text-sm font-medium text-ink">{item.title}</p>
            {item.description ? (
              <p className="mt-1 text-sm text-muted">{item.description}</p>
            ) : null}
            {item.action ? (
              <button
                type="button"
                className="mt-2 text-sm font-medium text-accent hover:underline"
                onClick={item.action.onClick}
              >
                {item.action.label}
              </button>
            ) : null}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
