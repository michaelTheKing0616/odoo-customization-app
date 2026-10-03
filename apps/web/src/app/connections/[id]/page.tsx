"use client";

import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import "@/styles/studio-refinement.css";
import { OverviewPageView } from "@/components/overview/OverviewPageView";
import { useOverviewPage } from "@/components/overview/use-overview-page";

export default function BrowserPage() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const connectionId = params.id;
  const router = useRouter();
  const expertMode = searchParams.get("expert") === "1";
  const vm = useOverviewPage(connectionId);

  useEffect(() => {
    if (!expertMode) return;
    router.replace(`/connections/${connectionId}/expert`);
  }, [expertMode, connectionId, router]);

  if (expertMode) {
    return (
      <div className="mx-auto max-w-3xl p-6 text-sm text-muted" data-testid="expert-destination-redirect">
        Opening Odoo Expert…
      </div>
    );
  }

  return <OverviewPageView {...vm} />;
}
