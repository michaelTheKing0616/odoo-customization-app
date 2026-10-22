"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import {
  FleetCommandPageView,
  type FleetHarnessState,
} from "@/components/command/FleetCommandPageView";

const STATES = ["empty", "idle", "loading", "partial", "error"] as const;

function CommandHarnessInner() {
  const enabled = process.env.NEXT_PUBLIC_E2E === "1";
  const searchParams = useSearchParams();
  const raw = searchParams.get("state") || "idle";
  const state = (STATES.includes(raw as FleetHarnessState) ? raw : "idle") as FleetHarnessState;

  if (!enabled) {
    return <main className="p-6 text-sm text-muted">E2E harness disabled.</main>;
  }

  return (
    <FleetCommandPageView
      harnessState={state}
      clientCount={null}
      clientsHydrated
    />
  );
}

export default function CommandHarnessPage() {
  return (
    <Suspense fallback={<main className="p-6 text-sm text-muted">Loading harness...</main>}>
      <CommandHarnessInner />
    </Suspense>
  );
}
