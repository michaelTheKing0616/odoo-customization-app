"use client";

import { Suspense } from "react";
import ModuleSpecPageInner from "./ModuleSpecPageInner";

export default function ModuleSpecPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen bg-[#1a1218] px-6 py-10 text-[#8f7a88]">
          Loading ModuleSpec builder…
        </main>
      }
    >
      <ModuleSpecPageInner />
    </Suspense>
  );
}
