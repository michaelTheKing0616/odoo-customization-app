"use client";

import { useParams } from "next/navigation";
import type { ReactNode } from "react";
import { SuiteShell } from "@/components/suite/SuiteShell";

/** Configuration Suite stage 1 shell (spec 4.1). */
export default function SuiteLayout({ children }: { children: ReactNode }) {
  const params = useParams<{ id: string }>();
  return <SuiteShell connectionId={params.id}>{children}</SuiteShell>;
}
