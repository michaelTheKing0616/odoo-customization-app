"use client";

import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { BotApprovalCard } from "@/components/bots/BotApprovalCard";
import { Callout } from "@/components/ui/Callout";
import { Skeleton } from "@/components/ui/layout-primitives";
import { botApprovalsApi, type BotApproval } from "@/lib/api/bot-approvals";

function message(e: unknown) {
  return e instanceof Error && e.message
    ? e.message
    : "Something went wrong. Try again.";
}

export default function BotApprovalsPage() {
  const { id: connectionId } = useParams<{ id: string }>();
  const [items, setItems] = useState<BotApproval[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState<{
    id: string;
    kind: "approve" | "reject";
  } | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      const res = await botApprovalsApi.list(connectionId);
      setItems(res.items);
      setLoadError(null);
    } catch (e) {
      setLoadError(message(e));
    }
  }, [connectionId]);

  useEffect(() => {
    void load();
  }, [load]);

  const decide = async (id: string, kind: "approve" | "reject") => {
    setBusy({ id, kind });
    setErrors((m) => ({ ...m, [id]: "" }));
    try {
      const updated = await botApprovalsApi[kind](connectionId, id);
      setItems((list) =>
        (list ?? []).map((it) => (it.id === id ? updated : it)),
      );
    } catch (e) {
      setErrors((m) => ({ ...m, [id]: message(e) }));
      void load();
    } finally {
      setBusy(null);
    }
  };

  const pending = (items ?? []).filter((i) => i.status === "pending");
  const others = (items ?? []).filter((i) => i.status !== "pending");

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold text-ink">Bot approvals</h1>
        <p className="text-sm text-muted">
          Bigger or riskier bot changes wait here until you say yes. Each
          approval covers this exact plan and record count, once.
        </p>
      </header>

      {loadError && (
        <Callout
          variant="warning"
          title="Couldn't load approvals"
          testId="bot-approvals-error"
        >
          {loadError}
        </Callout>
      )}

      {items === null && !loadError && <Skeleton className="h-40 w-full" />}

      {items !== null && pending.length === 0 && (
        <p className="text-sm text-muted" data-testid="bot-approvals-empty">
          Nothing is waiting for you.
        </p>
      )}

      {pending.map((it) => (
        <BotApprovalCard
          key={it.id}
          item={it}
          busy={busy?.id === it.id ? busy.kind : null}
          locked={busy !== null}
          error={errors[it.id] || null}
          onApprove={(id) => void decide(id, "approve")}
          onReject={(id) => void decide(id, "reject")}
        />
      ))}

      {others.length > 0 && (
        <section aria-label="Earlier plans" className="flex flex-col gap-4">
          <h2 className="text-sm font-medium text-muted">Earlier plans</h2>
          {others.map((it) => (
            <BotApprovalCard key={it.id} item={it} />
          ))}
        </section>
      )}
    </main>
  );
}
