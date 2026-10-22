"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { OpsHubPageView } from "@/components/operations/OpsHubPageView";

const STATES = ["idle"] as const;
type HarnessState = (typeof STATES)[number];

function OperationsHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "idle";
  const state = (STATES.includes(raw as HarnessState) ? raw : "idle") as HarnessState;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return <OpsHubPageView connectionId="demo-conn" harnessState={state} />;
}

export default function OperationsHarnessPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading harness...</main>}>
      <OperationsHarnessInner />
    </Suspense>
  );
}
