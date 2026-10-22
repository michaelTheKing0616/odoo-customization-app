"use client";

import { useParams } from "next/navigation";
import { Suspense } from "react";
import { ChangeRecords } from "@/components/suite/ChangeRecords";
import { RecordEditor } from "@/components/suite/RecordEditor";

export default function Page() {
  const { tool } = useParams<{ tool: string }>();
  return <Suspense>{tool === "records" ? <RecordEditor /> : <ChangeRecords tool={tool} />}</Suspense>;
}
