"use client";

import { Suspense } from "react";
import { Skeleton } from "@/components/ui/layout-primitives";
import ProjectsPageInner from "./ProjectsPageInner";
import "@/styles/studio-refinement.css";

function ProjectsPageFallback() {
  return (
    <main className="studio-refinement min-h-screen px-6 py-10" data-testid="projects-page-loading">
      <Skeleton className="h-8 w-56" />
      <Skeleton className="mt-6 h-24 w-full max-w-md" />
      <Skeleton className="mt-3 h-20 w-full max-w-md" />
    </main>
  );
}

export default function ProjectsPage() {
  return (
    <Suspense fallback={<ProjectsPageFallback />}>
      <ProjectsPageInner />
    </Suspense>
  );
}
