"use client";

import Link from "next/link";
import { FormEvent, Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Card, PageHeader } from "@/components/ui/layout-primitives";

function ResetPasswordContent() {
  const params = useSearchParams();
  const token = params.get("token") ?? "";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function requestReset(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.accountRequestPasswordReset(email);
      setNotice("If that email exists, a reset link was sent.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  async function submitNewPassword(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.accountResetPassword(token, password);
      setNotice(res.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      {error ? <ErrorNotice message={error} /> : null}
      {notice ? <Callout variant="info" title="Done">{notice}</Callout> : null}
      {token ? (
        <form className="space-y-4" onSubmit={submitNewPassword}>
          <label className="block space-y-1 text-sm">
            <span>New password</span>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={10}
              required
            />
          </label>
          <Button type="submit" disabled={busy}>
            Update password
          </Button>
        </form>
      ) : (
        <form className="space-y-4" onSubmit={requestReset}>
          <label className="block space-y-1 text-sm">
            <span>Email</span>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <Button type="submit" disabled={busy}>
            Send reset link
          </Button>
        </form>
      )}
      <Callout variant="info" title="Back" className="mt-4">
        <Link href="/login" className="underline">
          Log in
        </Link>
      </Callout>
    </Card>
  );
}

export default function ResetPasswordPage() {
  return (
    <div className="mx-auto max-w-md space-y-6 p-6">
      <PageHeader title="Reset password" description="We'll email you a reset link or set a new password." />
      <Suspense fallback={<Card><p className="text-sm text-muted-foreground">Loading…</p></Card>}>
        <ResetPasswordContent />
      </Suspense>
    </div>
  );
}
