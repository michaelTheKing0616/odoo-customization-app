"use client";

import { useParams } from "next/navigation";
import { CodeRunnerEditor } from "@/components/code-runner/CodeRunnerEditor";

export default function Page() {
  const { id } = useParams<{ id: string }>();
  return <CodeRunnerEditor connectionId={id} />;
}
