"use client";

import { useParams } from "next/navigation";
import { CodeStudioScreen } from "@/components/code-studio/CodeStudioScreen";
import "@/components/code-studio/code-studio-operate.css";

/** UI-S-18 Code Studio. Primary: Validate. The screen lives in components/code-studio. */
export default function CodeStudioPage() {
  const params = useParams<{ id: string }>();
  return <CodeStudioScreen connectionId={params.id} />;
}
