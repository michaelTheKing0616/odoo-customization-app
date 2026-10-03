"use client";

import { useParams } from "next/navigation";
import { StudioPageView } from "@/components/studio/StudioPageView";
import { useStudioPage } from "@/components/studio/use-studio-page";
import "@/styles/studio-refinement.css";

export default function AppStudioPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const vm = useStudioPage(connectionId);
  return <StudioPageView {...vm} />;
}
