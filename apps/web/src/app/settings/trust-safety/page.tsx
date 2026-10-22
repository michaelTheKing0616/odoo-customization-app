"use client";

import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import Link from "next/link";
import { api } from "@/lib/api";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Card, PageHeader, Skeleton } from "@/components/ui/layout-primitives";

export default function TrustSafetyPage() {
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getSafetyContract()
      .then((doc) => setMarkdown(doc.markdown))
      .catch((err: Error) => setError(err.message));
  }, []);

  return (
    <div className="mx-auto max-w-3xl" data-testid="trust-safety-page">
      <PageHeader
        title="Trust & safety"
        description="The honest contract for live Odoo mutation on your connections."
        actions={
          <Link href="/settings" className="text-sm text-accent hover:underline">
            Back to settings
          </Link>
        }
      />
      {error ? <ErrorNotice message={error} className="mt-4" /> : null}
      <Callout variant="info" title="Production write mode" className="mt-6">
        Complete the production readiness checklist on each connection Overview before unlocking
        production mode.
      </Callout>
      {markdown ? (
        <Card className="prose prose-sm mt-6 max-w-none p-6 dark:prose-invert">
          <Markdown>{markdown}</Markdown>
        </Card>
      ) : !error ? (
        <Card className="mt-6 space-y-3 p-6" role="status" data-testid="trust-safety-loading">
          <span className="sr-only">Loading the safety contract.</span>
          <div className="space-y-3" aria-hidden>
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-11/12" />
            <Skeleton className="h-4 w-4/5" />
            <Skeleton className="mt-4 h-6 w-40" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        </Card>
      ) : null}
    </div>
  );
}
