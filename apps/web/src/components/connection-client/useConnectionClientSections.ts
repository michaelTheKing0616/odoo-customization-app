"use client";

import { useCallback, useEffect, useState } from "react";
import { api, type Connection, type InboxPlan, type SnapshotRow } from "@/lib/api";
import type { ClientSectionState } from "./ClientSectionCard";

const OPEN_PLAN_STATUSES = new Set(["pending"]);

export function isOpenChangeSet(plan: InboxPlan): boolean {
  return OPEN_PLAN_STATUSES.has(plan.status);
}

export function useConnectionClientSections(connectionId: string) {
  const [connectionState, setConnectionState] = useState<ClientSectionState<Connection>>({
    phase: "loading",
  });
  const [changesState, setChangesState] = useState<ClientSectionState<InboxPlan[]>>({
    phase: "loading",
  });
  const [snapshotState, setSnapshotState] = useState<ClientSectionState<SnapshotRow | null>>({
    phase: "loading",
  });

  const loadConnection = useCallback(async () => {
    setConnectionState({ phase: "loading" });
    try {
      const connection = await api.getConnection(connectionId);
      setConnectionState({ phase: "ready", data: connection });
    } catch {
      setConnectionState({
        phase: "error",
        message: "Connection details could not be loaded. Retry keeps the rest of this page visible.",
      });
    }
  }, [connectionId]);

  const loadChanges = useCallback(async () => {
    setChangesState({ phase: "loading" });
    try {
      const body = await api.listInboxPlans(connectionId);
      const open = body.plans.filter(isOpenChangeSet);
      setChangesState({ phase: "ready", data: open });
    } catch {
      setChangesState({
        phase: "error",
        message: "Open change-sets could not be loaded. Check access and try again.",
      });
    }
  }, [connectionId]);

  const loadSnapshot = useCallback(async () => {
    setSnapshotState({ phase: "loading" });
    try {
      const rows = await api.listSnapshots(connectionId);
      setSnapshotState({ phase: "ready", data: rows[0] ?? null });
    } catch {
      setSnapshotState({
        phase: "error",
        message: "The last snapshot could not be loaded. Retry does not affect other sections.",
      });
    }
  }, [connectionId]);

  useEffect(() => {
    void loadConnection();
    void loadChanges();
    void loadSnapshot();
  }, [loadConnection, loadChanges, loadSnapshot]);

  return {
    connectionState,
    changesState,
    snapshotState,
    retryConnection: loadConnection,
    retryChanges: loadChanges,
    retrySnapshot: loadSnapshot,
  };
}
