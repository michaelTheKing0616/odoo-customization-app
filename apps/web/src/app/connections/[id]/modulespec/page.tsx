"use client";

import { Suspense } from "react";
import ModuleSpecPageInner from "./ModuleSpecPageInner";

export default function ModuleSpecPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-surface-raised px-6 py-10 text-muted">
          Loading ModuleSpec builder…
        </main>
      }
    >
      <ModuleSpecPageInner />
    </Suspense>
  );
}
