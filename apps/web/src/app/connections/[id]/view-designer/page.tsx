"use client";

import { useParams, useSearchParams } from "next/navigation";
import { ViewDesignerShell } from "@/components/view-designer/ViewDesignerShell";
import { DesignerDraftHandoff } from "@/components/view-designer/DesignerDraftHandoff";

/** Builders stage 1: View Designer on the shared view engine. ?draft= shows an App Studio view handed over before install. */
export default function ViewDesignerPage() {
  const params = useParams<{ id: string }>();
  const search = useSearchParams();
  const draft = search?.get("draft");
  if (draft) return <DesignerDraftHandoff connectionId={params.id} draftKey={draft} model={search?.get("model") ?? ""} />;
  return <ViewDesignerShell connectionId={params.id} />;
}
