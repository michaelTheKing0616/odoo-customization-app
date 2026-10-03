"use client";

import { Suspense } from "react";
import { Skeleton } from "@/components/ui/layout-primitives";
import ModuleSpecPageInner from "./ModuleSpecPageInner";
import "@/styles/studio-refinement.css";

function ModuleSpecPageFallback() {
  return (
    <main className="studio-refinement min-h-screen px-6 py-10" data-testid="modulespec-page-loading">
      <Skeleton className="h-8 w-64" />
      <Skeleton className="mt-6 h-32 w-full" />
      <Skeleton className="mt-3 h-48 w-full" />
    </main>
  );
}

export default function ModuleSpecPage() {
  return (
    <Suspense fallback={<ModuleSpecPageFallback />}>
      <ModuleSpecPageInner />
    </Suspense>
  );
}
