"use client";

import { useParams } from "next/navigation";
import { ReportDesignerShell } from "@/components/report-designer/ReportDesignerShell";

/** Builders stage 1: Report Designer with the real PDF from Odoo. */
export default function ReportDesignerPage() {
  const params = useParams<{ id: string }>();
  return <ReportDesignerShell connectionId={params.id} />;
}
