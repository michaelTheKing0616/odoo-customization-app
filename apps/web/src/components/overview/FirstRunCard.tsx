"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/layout-primitives";

type Props = {
  connectionId: string;
  modelCount: number;
};

function storageKey(connectionId: string) {
  return `overview-first-run-dismissed-${connectionId}`;
}

export function FirstRunCard({ connectionId, modelCount }: Props) {
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    if (modelCount > 0) return;
    try {
      setDismissed(localStorage.getItem(storageKey(connectionId)) === "1");
    } catch {
      setDismissed(false);
    }
  }, [connectionId, modelCount]);

  if (modelCount > 0 || dismissed) return null;

  return (
    <Card className="mt-6 p-5" data-testid="overview-first-run">
      <h2 className="text-lg font-semibold text-ink">Start here</h2>
      <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-muted">
        <li>
          <span className="text-ink">Connect</span> — this instance is linked.
        </li>
        <li>
          <Link href={`/connections/${connectionId}/wizard`} className="text-accent hover:underline">
            Draft with AI
          </Link>{" "}
          — describe your app and review a ModuleSpec before anything touches Odoo.
        </li>
        <li>
          <Link href={`/connections/${connectionId}/builder`} className="text-accent hover:underline">
            Apply in Builder
          </Link>{" "}
          — create models and fields, or export as a module.
        </li>
      </ol>
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="mt-4"
        onClick={() => {
          localStorage.setItem(storageKey(connectionId), "1");
          setDismissed(true);
        }}
        data-testid="overview-first-run-dismiss"
      >
        Dismiss
      </Button>
    </Card>
  );
}
