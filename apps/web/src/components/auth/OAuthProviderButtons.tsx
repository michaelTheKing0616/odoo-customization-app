"use client";

import { useEffect, useState } from "react";
import { api, getApiBase } from "@/lib/api";
import { Button } from "@/components/ui/Button";

const LABELS: Record<string, string> = {
  google: "Continue with Google",
  github: "Continue with GitHub",
};

export function OAuthProviderButtons() {
  const [providers, setProviders] = useState<string[]>([]);

  useEffect(() => {
    api
      .accountOAuthProviders()
      .then((res) => setProviders(res.providers))
      .catch(() => setProviders([]));
  }, []);

  if (providers.length === 0) {
    return null;
  }

  return (
    <div className="space-y-2">
      <p className="text-center text-xs text-muted">Or continue with</p>
      {providers.map((provider) => (
        <Button
          key={provider}
          type="button"
          variant="secondary"
          className="w-full"
          onClick={() => {
            window.location.href = `${getApiBase()}/api/accounts/oauth/${provider}/start`;
          }}
        >
          {LABELS[provider] ?? `Continue with ${provider}`}
        </Button>
      ))}
    </div>
  );
}
