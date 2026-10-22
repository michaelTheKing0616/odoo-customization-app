"use client";

import { useParams } from "next/navigation";
import { OpsHubPageView } from "@/components/operations/OpsHubPageView";

export default function OperationsHubPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;

  return <OpsHubPageView connectionId={connectionId} />;
}
