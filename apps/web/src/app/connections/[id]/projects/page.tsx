"use client";

import { Suspense } from "react";
import ProjectsPageInner from "./ProjectsPageInner";
import "@/styles/studio-refinement.css";

export default function ProjectsPage() {
  return (
    <Suspense
      fallback={
        <main className="studio-refinement min-h-screen px-6 py-10 text-muted">
          Loading projects board…
        </main>
      }
    >
      <ProjectsPageInner />
    </Suspense>
  );
}
