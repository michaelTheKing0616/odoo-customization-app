"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import {
  WebsiteEditor,
  type WebsitePageSummary,
} from "@/components/website/WebsiteEditor";
import { api } from "@/lib/api";

export default function WebsiteEditorPage() {
  const params = useParams<{ id: string }>();
  const connectionId = params.id;
  const [pages, setPages] = useState<WebsitePageSummary[]>([]);
  const [available, setAvailable] = useState(true);
  const [reason, setReason] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listWebsitePages(connectionId)
      .then((res) => {
        setAvailable(res.available);
        setReason(res.reason);
        setPages(res.pages ?? []);
      })
      .catch((e: Error) => setError(e.message));
  }, [connectionId]);

  if (error) {
    return (
      <main className="p-6 text-sm text-danger" data-testid="website-editor-page">
        {error}
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
      />
    </main>
  );
}
