"use client";

import Link from "next/link";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { OAuthProviderButtons } from "@/components/auth/OAuthProviderButtons";
import { Button } from "@/components/ui/Button";
import { ErrorNotice } from "@/components/ui/ErrorNotice";
import { TotpCodeInput } from "@/components/auth/TotpCodeInput";
import { Input } from "@/components/ui/Input";
import { Card, PageHeader } from "@/components/ui/layout-primitives";
import { isCompleteTotpCode, totpCodeError } from "@/lib/auth/totp";

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
  const [codeError, setCodeError] = useState<string | null>(null);
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
    const invalidCode = totpCodeError(totpCode, oauthTotp);
    if (invalidCode) {
      setCodeError(invalidCode);
      return;
    }
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
            : "Access your Ingenium workspace."
        }
      />
      <Card className="space-y-5 p-5">
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
          <TotpCodeInput
            label="Two-factor code"
            description={
              oauthTotp
                ? "The 6 digits shown in your authenticator app."
                : "Only if two-factor sign-in is on for your account. Leave blank otherwise."
            }
            value={totpCode}
            onChange={(next) => {
              setTotpCode(next);
              setCodeError(null);
            }}
            error={codeError}
            required={oauthTotp}
            busy={busy}
            autoFocus={oauthTotp}
          />
          <Button
            type="submit"
            variant="primary"
            className="w-full"
            disabled={busy || (oauthTotp && !isCompleteTotpCode(totpCode))}
          >
            {busy ? "Signing in…" : oauthTotp ? "Complete sign-in" : "Sign in"}
          </Button>
        </form>
        {!oauthTotp ? <OAuthProviderButtons /> : null}
        {!oauthTotp ? (
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border-subtle pt-4 text-sm text-muted">
            <p>
              New here?{" "}
              <Link href="/signup" className="text-ink underline underline-offset-2 hover:text-accent">
                Create an account
              </Link>
            </p>
            <Link
              href="/reset-password"
              className="text-ink underline underline-offset-2 hover:text-accent"
            >
              Forgot your password?
            </Link>
          </div>
        ) : null}
      </Card>
    </div>
  );
}
