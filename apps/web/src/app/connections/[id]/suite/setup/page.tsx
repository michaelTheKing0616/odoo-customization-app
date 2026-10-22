"use client";

import { Suspense } from "react";
import { SetupWorkspace } from "@/components/suite/SetupWorkspace";

export default function Page() {
  return <Suspense fallback={null}><SetupWorkspace /></Suspense>;
}
