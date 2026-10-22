"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { PlanInboxView, type PlanInboxPhase } from "@/components/plan-inbox/PlanInboxView";
import type { PlanDecisionState } from "@/components/plan-inbox/PlanLedger";
import { fetchApi } from "@/lib/api/client";
import "@/components/plan-inbox/plan-inbox-operate.css";
import { announceFavicon } from "@/components/ui/craft";
import { readSnoozes, tomorrowMorningLagos, untilLabel, writeSnoozes, type SnoozeMap } from "@/lib/snooze";
import {
  decideFailure,
  decisionRecordedMessage,
  sortPlans,
  type InboxPlanCard,
  type PlanDecision,
} from "@/lib/planInboxScreen";

const IDLE_DECISION: PlanDecisionState = { busy: null, message: null, failure: null };

function syncUrl(connectionId: string, planHash: string | null) {
  if (typeof window === "undefined" || !connectionId) return;
  const params = new URLSearchParams({ connection_id: connectionId });
  if (planHash) params.set("plan", planHash);
  window.history.replaceState(window.history.state, "", `/approvals?${params.toString()}`);
}

/** UI-S-50 plan inbox route. Owns fetching, URL state, and decide calls. */
function ApprovalsInbox() {
  const searchParams = useSearchParams();
  const [connectionId, setConnectionId] = useState("");
  const [loadedConnectionId, setLoadedConnectionId] = useState("");
  const [phase, setPhase] = useState<PlanInboxPhase>("idle");
  const [plans, setPlans] = useState<InboxPlanCard[]>([]);
  const [selectedHash, setSelectedHash] = useState<string | null>(null);
  const [missingHash, setMissingHash] = useState<string | null>(null);
  const [viewerId, setViewerId] = useState<string | null>(null);
  const [staleHashes, setStaleHashes] = useState<ReadonlySet<string>>(() => new Set());
  const [decision, setDecision] = useState<PlanDecisionState>(IDLE_DECISION);
  useEffect(() => {
    announceFavicon({ count: plans.length });
    return () => announceFavicon({ count: 0 });
  }, [plans.length]);
  const [now, setNow] = useState(() => new Date());
  const [snoozes, setSnoozes] = useState<SnoozeMap>({});
  useEffect(() => setSnoozes(readSnoozes()), [now]);
  const snooze = (hash: string, until: number | null) => {
    const next = { ...readSnoozes() };
    if (until == null) delete next[hash];
    else next[hash] = until;
    writeSnoozes(next);
    setSnoozes(next);
  };
  const visible = plans.filter((p) => !snoozes[p.plan_hash] || p.plan_hash === selectedHash);
  const snoozedCount = plans.length - plans.filter((p) => !snoozes[p.plan_hash]).length;
  /** `strict` comes from a URL `plan=` id: missing means "not found". Otherwise it is a soft preference. */
  const requestedHashRef = useRef<{ hash: string; strict: boolean } | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchApi("/api/accounts/me")
      .then(async (res) => (res.ok ? ((await res.json()) as { user?: { id?: string } }) : null))
      .then((body) => {
        if (!cancelled) setViewerId(body?.user?.id ? String(body.user.id) : null);
      })
      .catch(() => {
        if (!cancelled) setViewerId(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const lastRequestedRef = useRef<string | null>(null);

  const load = useCallback(async (target: string) => {
    const id = target.trim();
    if (!id) return;
    lastRequestedRef.current = id;
    setPhase("loading");
    setDecision(IDLE_DECISION);
    try {
      const response = await fetchApi(`/api/inbox/plans?connection_id=${encodeURIComponent(id)}`);
      let next: InboxPlanCard[] = [];
      if (response.status === 404) {
        next = [];
      } else if (!response.ok) {
        setPhase("error");
        setPlans([]);
        return;
      } else {
        const body = (await response.json()) as { plans?: InboxPlanCard[] };
        next = Array.isArray(body.plans) ? body.plans : [];
      }
      const clock = new Date();
      setNow(clock);
      setPlans(next);
      setLoadedConnectionId(id);
      setStaleHashes(new Set());
      const requested = requestedHashRef.current;
      requestedHashRef.current = null;
      const present = requested ? next.some((plan) => plan.plan_hash === requested.hash) : false;
      if (requested?.strict && !present) {
        setMissingHash(requested.hash);
        setSelectedHash(null);
      } else {
        setMissingHash(null);
        const pick = (present ? requested?.hash : null) ?? sortPlans(next, clock)[0]?.plan_hash ?? null;
        setSelectedHash(pick);
        syncUrl(id, pick);
      }
      setPhase("ready");
    } catch {
      setPhase("error");
      setPlans([]);
    }
  }, []);

  // Keyed on connection_id only: selecting a plan rewrites `plan=` in the URL and must not reload.
  const queryConnection = searchParams?.get("connection_id")?.trim() ?? "";
  useEffect(() => {
    if (!queryConnection || queryConnection === lastRequestedRef.current) return;
    const planParam = searchParams?.get("plan")?.trim();
    requestedHashRef.current = planParam ? { hash: planParam, strict: true } : null;
    setConnectionId(queryConnection);
    void load(queryConnection);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- read `plan` once per connection
  }, [queryConnection, load]);

  function select(hash: string) {
    setSelectedHash(hash);
    setMissingHash(null);
    setDecision(IDLE_DECISION);
    syncUrl(loadedConnectionId, hash);
  }

  async function decide(plan: InboxPlanCard, choice: PlanDecision) {
    if (!viewerId || !plan.schema_fp) return;
    setDecision({ busy: choice, message: null, failure: null });
    try {
      const response = await fetchApi(`/api/inbox/plans/${encodeURIComponent(plan.plan_hash)}/decide`, {
        method: "POST",
        body: JSON.stringify({
          connection_id: loadedConnectionId,
          approver_id: viewerId,
          user_id: viewerId,
          decision: choice,
          plan_hash: plan.plan_hash,
          schema_fp: plan.schema_fp,
        }),
      });
      if (!response.ok) {
        let code: string | undefined;
        try {
          const body = (await response.json()) as { detail?: { error?: string } };
          code = body?.detail?.error;
        } catch {
          code = undefined;
        }
        const failure = decideFailure(response.status, code);
        if (failure.kind === "stale") {
          setStaleHashes((prev) => new Set([...prev, plan.plan_hash]));
        }
        setDecision({ busy: null, message: null, failure });
        return;
      }
      const body = (await response.json()) as { card?: InboxPlanCard };
      const card: InboxPlanCard = { ...plan, ...(body.card ?? {}) };
      const clock = new Date();
      setNow(clock);
      setPlans((prev) => prev.map((item) => (item.plan_hash === plan.plan_hash ? card : item)));
      setDecision({ busy: null, message: decisionRecordedMessage(card, choice, clock), failure: null });
    } catch {
      setDecision({ busy: null, message: null, failure: decideFailure(null) });
    }
  }

  return (
    <>
    {selectedHash || snoozedCount ? (
      <div className="snooze-bar" data-testid="approvals-snooze">
        {selectedHash && !snoozes[selectedHash] ? (
          <>
            <span>Snooze this until</span>
            <button type="button" onClick={() => snooze(selectedHash, tomorrowMorningLagos())}>tomorrow, 8:00</button>
            <button type="button" onClick={() => snooze(selectedHash, Date.now() + 2 * 3_600_000)}>in 2 hours</button>
          </>
        ) : null}
        {selectedHash && snoozes[selectedHash] ? (
          <>
            <span>Snoozed until {untilLabel(snoozes[selectedHash])}.</span>
            <button type="button" onClick={() => snooze(selectedHash, null)}>Unsnooze</button>
          </>
        ) : null}
        {snoozedCount ? <span className="snooze-count">{snoozedCount} snoozed. Only on this device; the approval still waits.</span> : null}
      </div>
    ) : null}
    <PlanInboxView
      connectionId={connectionId}
      onConnectionChange={setConnectionId}
      onOpen={() => {
        requestedHashRef.current = null;
        void load(connectionId);
      }}
      onRefresh={() => {
        requestedHashRef.current = selectedHash ? { hash: selectedHash, strict: false } : null;
        void load(loadedConnectionId || connectionId);
      }}
      phase={phase}
      plans={visible}
      loadedConnectionId={loadedConnectionId}
      selectedHash={selectedHash}
      missingHash={missingHash}
      onSelect={select}
      viewerId={viewerId}
      staleHashes={staleHashes}
      decision={decision}
      onDecide={(plan, choice) => void decide(plan, choice)}
      now={now}
    />
    </>
  );
}

export default function ApprovalsPage() {
  return (
    <Suspense fallback={null}>
      <ApprovalsInbox />
    </Suspense>
  );
}
