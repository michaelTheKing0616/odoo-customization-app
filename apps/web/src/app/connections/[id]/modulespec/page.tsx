"use client";

import { Suspense } from "react";
import ModuleSpecPageInner from "./ModuleSpecPageInner";
import "@/styles/studio-refinement.css";

export default function ModuleSpecPage() {
  return (
    <Suspense
      fallback={
        <main className="studio-refinement min-h-screen px-6 py-10 text-muted">
          Loading ModuleSpec workbench…
        </main>
      }
    >
      <ModuleSpecPageInner />
    </Suspense>
  );
}
