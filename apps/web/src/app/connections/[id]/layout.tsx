"use client";

import { Suspense } from "react";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { QueryProvider } from "@/providers/QueryProvider";
import ConnectionLayoutInner from "./layout-inner";
import ConnectionLoading from "./loading";

export default function ConnectionLayout({ children }: { children: React.ReactNode }) {
  return (
    <QueryProvider>
      <ThemeProvider>
        <TooltipProvider>
          <Suspense fallback={<ConnectionLoading />}>
            <ConnectionLayoutInner>{children}</ConnectionLayoutInner>
          </Suspense>
        </TooltipProvider>
      </ThemeProvider>
    </QueryProvider>
  );
}
