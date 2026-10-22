"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { FleetCommandPageView } from "@/components/command/FleetCommandPageView";
import type { AccountSession } from "@/lib/api/auth";

function isClientApprover(role: string | undefined): boolean {
  return role === "client_approver";
}

export default function CommandCenterPage() {
  const router = useRouter();
  const [gate, setGate] = useState<"loading" | "consultant" | "redirecting">("loading");
  const [clientCount, setClientCount] = useState<number | null>(null);
  const [clientsHydrated, setClientsHydrated] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function run() {
      try {
        const meRes = await fetch("/api/accounts/me");
        if (meRes.ok) {
          const session = (await meRes.json()) as AccountSession;
          if (isClientApprover(session.workspace.role)) {
            const connRes = await fetch("/api/connections");
            const connections = connRes.ok
              ? ((await connRes.json()) as Array<{ id: string }>)
              : [];
            const connectionId = connections[0]?.id;
            if (!cancelled) {
              setGate("redirecting");
              router.replace(
                connectionId
                  ? `/approvals?connection_id=${encodeURIComponent(connectionId)}`
                  : "/approvals",
              );
            }
            return;
          }
        }
      } catch {
        /* auth off or network — show consultant home */
      }
      if (!cancelled) {
        setGate("consultant");
      }
    }
    void run();
    return () => {
      cancelled = true;
    };
  }, [router]);

  useEffect(() => {
    if (gate !== "consultant") {
      return;
    }
    let cancelled = false;
    async function loadClients() {
      setClientsHydrated(false);
      try {
        const response = await fetch("/api/command/tiles/clients");
        if (response.ok) {
          const body = (await response.json()) as { count: number };
          if (!cancelled) {
            setClientCount(body.count);
          }
        } else if (!cancelled) {
          setClientCount(null);
        }
      } catch {
        if (!cancelled) {
          setClientCount(null);
        }
      } finally {
        if (!cancelled) {
          setClientsHydrated(true);
        }
      }
    }
    void loadClients();
    return () => {
      cancelled = true;
    };
  }, [gate]);

  if (gate === "loading" || gate === "redirecting") {
    return <FleetCommandPageView gateLoading clientCount={null} clientsHydrated={false} />;
  }

  return (
    <FleetCommandPageView clientCount={clientCount} clientsHydrated={clientsHydrated} />
  );
}
