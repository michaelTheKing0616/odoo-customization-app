"use client";

import Link from "next/link";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { OAuthProviderButtons } from "@/components/auth/OAuthProviderButtons";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { Input } from "@/components/ui/Input";
import { Card, PageHeader } from "@/components/ui/layout-primitives";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="mx-auto max-w-md p-6 text-sm text-muted">Loading sign-in…</div>
      }
    >
      <LoginPageContent />
    </Suspense>
  );
}

function LoginPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const oauthTotp = searchParams.get("oauth_totp") === "1";
  const oauthToken = searchParams.get("token") ?? "";
  const oauthError = searchParams.get("oauth_error");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [error, setError] = useState<string | null>(
    oauthError ? `Sign-in could not be completed (${oauthError}).` : null,
  );
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (oauthError) {
      setError(`Sign-in could not be completed (${oauthError}).`);
    }
  }, [oauthError]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (oauthTotp && oauthToken) {
        await api.accountOAuthComplete2FA({ token: oauthToken, totp_code: totpCode });
      } else {
        await api.accountLogin({
          email,
          password,
          ...(totpCode ? { totp_code: totpCode } : {}),
        });
      }
      router.push("/connect");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md space-y-6 p-6">
      <PageHeader
        title={oauthTotp ? "Complete sign-in" : "Log in"}
        description={
          oauthTotp
            ? "Enter your two-factor code to finish OAuth sign-in."
            : "Access your Odoo Custom workspace."
        }
      />
      <Card>
        <form className="space-y-4" onSubmit={onSubmit}>
          {error ? <ErrorNotice message={error} /> : null}
          {!oauthTotp ? (
            <>
              <label className="block space-y-1 text-sm">
                <span>Email</span>
                <Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              </label>
              <label className="block space-y-1 text-sm">
                <span>Password</span>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </label>
            </>
          ) : null}
          <label className="block space-y-1 text-sm">
            <span>2FA code{oauthTotp ? "" : " (if enabled)"}</span>
            <Input
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value)}
              required={oauthTotp}
            />
          </label>
          <Button type="submit" disabled={busy}>
            {busy ? "Signing in…" : oauthTotp ? "Complete sign-in" : "Sign in"}
          </Button>
        </form>
        {!oauthTotp ? <OAuthProviderButtons /> : null}
        <Callout variant="info" title="New here?" className="mt-4">
          <Link href="/signup" className="underline">
            Create an account
          </Link>
          {" · "}
          <Link href="/reset-password" className="underline">
            Forgot password
          </Link>
        </Callout>
      </Card>
    </div>
  );
}
