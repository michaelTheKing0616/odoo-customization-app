"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Card, PageHeader } from "@/components/ui/layout-primitives";

function VerifyContent() {
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!token) {
      setError("Missing verification token.");
      return;
    }
    api
      .accountVerifyEmail(token)
      .then((res) => setMessage(res.message))
      .catch((err) => setError(err instanceof Error ? err.message : "Verification failed"));
  }, [token]);

  return (
    <Card>
      {error ? <ErrorNotice message={error} /> : null}
      {message ? (
        <Callout variant="info" title="Verified">
          {message}{" "}
          <Link href="/login" className="underline">
            Log in
          </Link>
        </Callout>
      ) : null}
      {!error && !message ? <p className="text-sm text-muted-foreground">Verifying…</p> : null}
    </Card>
  );
}

export default function VerifyPage() {
  return (
    <div className="mx-auto max-w-md space-y-6 p-6">
      <PageHeader title="Verify email" />
      <Suspense fallback={<Card><p className="text-sm text-muted-foreground">Loading…</p></Card>}>
        <VerifyContent />
      </Suspense>
    </div>
  );
}
