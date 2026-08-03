"use client";

import { Suspense } from "react";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { ToastProvider } from "@/components/ui/Toast";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { QueryProvider } from "@/providers/QueryProvider";
import ConnectionLayoutInner from "./layout-inner";

export default function ConnectionLayout({ children }: { children: React.ReactNode }) {
  return (
    <QueryProvider>
      <ThemeProvider>
        <TooltipProvider>
          <ToastProvider>
            <Suspense
              fallback={
                <div className="flex min-h-screen items-center justify-center text-muted">
                  Loading shell…
                </div>
              }
            >
              <ConnectionLayoutInner>{children}</ConnectionLayoutInner>
            </Suspense>
          </ToastProvider>
        </TooltipProvider>
      </ThemeProvider>
    </QueryProvider>
  );
}
