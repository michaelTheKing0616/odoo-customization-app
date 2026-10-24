"use client";

/** BV-UI-WIRE: one verify run's evidence in the Bots area (D-BV-WIRE-1 = a). */
import { useParams } from "next/navigation";
import { VerifyRunPanel } from "@/components/bots/VerifyRunPanel";

export default function VerifyRunPage() {
  const params = useParams<{ id: string; runId: string }>();
  return (
    <div className="mx-auto w-full max-w-5xl min-w-0 px-4 py-6 sm:px-6">
      <h1 className="mb-4 text-ui-title font-semibold text-ink">Change check</h1>
      <VerifyRunPanel connectionId={params.id} runId={params.runId} />
    </div>
  );
}
