"use client";

import { useParams } from "next/navigation";
import { WireframeUploadView } from "@/components/wireframe/WireframeUploadView";
import "@/styles/studio-refinement.css";

export default function WireframeUploadPage() {
  const params = useParams<{ id: string }>();
  return <WireframeUploadView connectionId={params.id} />;
}
