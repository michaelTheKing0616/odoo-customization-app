"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";
import { api } from "@/lib/api";
import { OAuthProviderButtons } from "@/components/auth/OAuthProviderButtons";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Card, PageHeader } from "@/components/ui/layout-primitives";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.accountSignup({
        email,
        password,
        workspace_name: workspaceName || undefined,
      });
      setNotice("Account created — check your email to verify before logging in.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Signup failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-6 p-6">
      <PageHeader title="Create account" description="Start your Odoo Custom workspace." />
      <Card>
        <form className="space-y-4" onSubmit={onSubmit}>
          {error ? <ErrorNotice message={error} /> : null}
          {notice ? <Callout variant="info" title="Success">{notice}</Callout> : null}
          <label className="block space-y-1 text-sm">
            <span>Email</span>
            <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label className="block space-y-1 text-sm">
            <span>Password (min 10 characters)</span>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={10}
              required
            />
          </label>
          <label className="block space-y-1 text-sm">
            <span>Workspace name</span>
            <Input value={workspaceName} onChange={(e) => setWorkspaceName(e.target.value)} />
          </label>
          <Button type="submit" disabled={busy}>
            {busy ? "Creating…" : "Sign up"}
          </Button>
        </form>
        <OAuthProviderButtons />
        <Callout variant="info" title="Already have an account?" className="mt-4">
          <Link href="/login" className="underline">
            Log in
          </Link>
        </Callout>
      </Card>
    </div>
  );
}
