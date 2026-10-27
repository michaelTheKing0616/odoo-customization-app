"use client";

import Link from "next/link";
import { BotAvatar, BotPresenceChip } from "@/components/avatars/BotAvatar";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { EmptyState } from "@/components/ui/layout-primitives";
import { Badge } from "@/components/ui/Badge";
import { BOT_ROLES, displayName, type BotState } from "@/lib/avatars/playback";
import { ClientSectionCard } from "./ClientSectionCard";
import { useConnectionClientSections } from "./useConnectionClientSections";

type Props = {
  connectionId: string;
};

function formatWhen(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export function ConnectionClientPanel({ connectionId }: Props) {
  const {
    connectionState,
    changesState,
    snapshotState,
    retryConnection,
    retryChanges,
    retrySnapshot,
  } = useConnectionClientSections(connectionId);

  return (
    <div className="grid gap-4 lg:grid-cols-2" data-testid="connection-client-panel">
      <ClientSectionCard
        testId="connection-client-connection"
        title="Connection"
        description="Odoo instance linked to this workspace grant."
        state={connectionState}
        onRetry={() => void retryConnection()}
        renderReady={(connection) => (
          <dl className="space-y-2 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <dt className="sr-only">Name</dt>
              <dd className="font-medium text-ink">{connection.name}</dd>
              <Badge variant="default">{connection.write_mode}</Badge>
              {connection.server_version ? (
                <Badge variant="info">{connection.server_version}</Badge>
              ) : null}
            </div>
            <div>
              <dt className="text-xs text-muted">URL</dt>
              <dd className="font-mono text-xs text-ink">{connection.url}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Database</dt>
              <dd className="font-mono text-xs text-ink">{connection.db_name}</dd>
            </div>
          </dl>
        )}
      />

      <ClientSectionCard
        testId="connection-client-changesets"
        title="Open change-sets"
        description="Validated plans still waiting on approval for this connection."
        state={changesState}
        onRetry={() => void retryChanges()}
        isEmpty={(plans) => plans.length === 0}
        renderEmpty={() => (
          <EmptyState
            title="No open change-sets"
            description="When the engine submits a plan that still needs approval, it will appear here."
            action={
              <Button variant="secondary" size="sm" asChild>
                <Link href={`/approvals?connection_id=${encodeURIComponent(connectionId)}`}>
                  Open approval inbox
                </Link>
              </Button>
            }
          />
        )}
        renderReady={(plans) => (
          <ul className="space-y-2">
            {plans.map((plan) => (
              <li
                key={plan.plan_hash}
                className="rounded-md border border-border-subtle bg-surface px-3 py-2"
                data-testid="connection-client-open-plan"
              >
                <p className="text-sm font-medium text-ink">{plan.goal}</p>
                <p className="mt-1 font-mono text-xs text-muted">
                  {plan.plan_hash.slice(0, 12)}… · {plan.max_risk} · {plan.environment}
                </p>
                <p className="mt-1 text-xs text-muted">Expires {formatWhen(plan.expires_at)}</p>
              </li>
            ))}
            <li>
              <Link
                href={`/approvals?connection_id=${encodeURIComponent(connectionId)}`}
                className="text-sm text-accent hover:underline"
              >
                Review in approval inbox
              </Link>
            </li>
          </ul>
        )}
      />

      <ClientSectionCard
        testId="connection-client-snapshot"
        title="Last snapshot"
        description="Most recent metadata snapshot saved before a gated write."
        state={snapshotState}
        onRetry={() => void retrySnapshot()}
        isEmpty={(snap) => snap === null}
        renderEmpty={() => (
          <EmptyState
            title="No snapshots yet"
            description="Snapshots appear after the first reversible write on this connection."
            action={
              <Button variant="secondary" size="sm" asChild>
                <Link href={`/connections/${connectionId}/journal`}>Open journal</Link>
              </Button>
            }
          />
        )}
        renderReady={(snap) => snap === null ? null : (
          <div className="space-y-2 text-sm">
            <p className="font-medium text-ink">{snap.label}</p>
            <p className="font-mono text-xs text-muted">{snap.id}</p>
            <p className="text-xs text-muted">
              {snap.resource_type} · {snap.reversible} · {formatWhen(snap.created_at)}
            </p>
            <Link
              href={`/connections/${connectionId}/journal`}
              className="inline-block text-sm text-accent hover:underline"
            >
              All snapshots in journal
            </Link>
          </div>
        )}
      />

      <CardBotRosterPlaceholder />
    </div>
  );
}

function CardBotRosterPlaceholder() {
  const presence: BotState[] = ["idle", "thinking", "waiting_approval", "blocked", "done"];
  return (
    <div className="space-y-3">
      <Callout
        variant="info"
        title="Bot roster"
        testId="connection-client-bot-roster"
      >
        Worker bot roster is not available yet for this connection. When Track 8 ships bot
        management, assigned bots will list here — nothing is shown until that API exists.
      </Callout>
      <section className="space-y-3" aria-label="Example bot roster" data-testid="connection-client-bot-roster-example">
        <p className="text-xs text-muted">Example</p>
        <ul className="flex flex-wrap gap-3">
          {BOT_ROLES.map((role) => (
            <li key={role} className="flex w-28 flex-col items-center gap-1 text-center">
              <BotAvatar role={role} state="idle" size={48} />
              <span className="text-xs text-ink">{displayName(role)}</span>
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap gap-2" aria-label="Example presence">
          {presence.map((state) => (
            <BotPresenceChip key={state} role="chief_of_staff" state={state} />
          ))}
        </div>
      </section>
    </div>
  );
}
