"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";

import {
  WebsiteEditor,
  type WebsitePageSummary,
} from "@/components/website/WebsiteEditor";
import { formatWebsiteError } from "@/components/website/websiteError";
import { api } from "@/lib/api";

export default function WebsiteEditorPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const [pages, setPages] = useState<WebsitePageSummary[]>([]);
  const [available, setAvailable] = useState(true);
  const [reason, setReason] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [listHydrated, setListHydrated] = useState(false);

  const refreshPages = useCallback(() => {
    setListHydrated(false);
    setError(null);
    api
      .listWebsitePages(connectionId)
      .then((res) => {
        setAvailable(res.available);
        setReason(res.reason);
        setPages(res.pages ?? []);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setListHydrated(true));
  }, [connectionId]);

  useEffect(() => {
    refreshPages();
  }, [refreshPages]);

  if (error) {
    const parts = formatWebsiteError(error);
    return (
      <main className="mx-auto max-w-5xl p-6" data-testid="website-editor-page">
        <div
          className="rounded-md border border-danger/30 bg-danger-subtle p-4 text-sm"
          role="alert"
          data-testid="website-error"
        >
          <p className="font-semibold" data-testid="website-error-what">
            {parts.what}
          </p>
          <p className="mt-2 text-xs font-medium uppercase tracking-wide text-muted">
            Why
          </p>
          <p className="mt-1 text-muted" data-testid="website-error-why">
            {parts.why}
          </p>
          <p className="mt-2 text-xs font-medium uppercase tracking-wide text-muted">
            Next
          </p>
          <p className="mt-1 text-muted" data-testid="website-error-next">
            {parts.next}
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="p-6" data-testid="website-editor-page">
      <WebsiteEditor
        connectionId={connectionId}
        pages={pages}
        pagesAvailable={available}
        unavailableReason={reason}
        pagesLoading={!listHydrated}
        onRefreshPages={refreshPages}
      />
    </main>
  );
}
