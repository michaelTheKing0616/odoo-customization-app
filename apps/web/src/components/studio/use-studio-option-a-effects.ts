"use client";

import { useEffect } from "react";
import { api } from "@/lib/api";
import { odooViewUrl, preferHostListActionId } from "@/lib/odoo-urls";
import type { StudioState } from "./use-studio-state";
import type { StudioDerived } from "./use-studio-derived";

export function useStudioOptionAEffects(
  connectionId: string,
  s: Pick<
    StudioState,
    "connection" | "setGoldHost" | "setOdooAppUrl" | "setSession"
  >,
  d: Pick<
    StudioDerived,
    | "goldOptionA"
    | "goldId"
    | "optionAHostLive"
    | "hostForOpen"
    | "applyTarget"
  >,
  goldPromoted: boolean,
) {
  const { connection, setGoldHost, setOdooAppUrl, setSession } = s;
  const { goldOptionA, goldId, optionAHostLive, hostForOpen, applyTarget } = d;

  useEffect(() => {
    if (!goldOptionA || !goldId) {
      setGoldHost(null);
      return;
    }
    let cancelled = false;
    api
      .goldInspect(connectionId, goldId)
      .then((row) => {
        if (!cancelled) setGoldHost(row);
      })
      .catch(() => {
        if (!cancelled) setGoldHost(null);
      });
    return () => {
      cancelled = true;
    };
  }, [connectionId, goldOptionA, goldId, goldPromoted, setGoldHost]);

  // After Option A Promote, resolve Quotations (etc.) act_window — bare model= lands on Discuss.
  useEffect(() => {
    if (!connectionId || goldOptionA) return;
    if (!(goldPromoted || optionAHostLive)) return;
    const host = hostForOpen;
    if (!host || applyTarget.openActionId) return;
    const base = connection?.url?.replace(/\/$/, "") || "";
    if (!base) return;
    let cancelled = false;
    (async () => {
      try {
        const actions = await api.listWindowActions(connectionId, {
          model: host,
          standaloneOnly: true,
        });
        if (cancelled) return;
        const actionId = preferHostListActionId(actions, host);
        if (!actionId) return;
        const href = odooViewUrl(base, host, "list", actionId);
        setOdooAppUrl(href);
        setSession((cur) => {
          if (!cur?.artifact) return cur;
          const prev = cur.artifact._studio_apply;
          const prior =
            prev && typeof prev === "object" && !Array.isArray(prev)
              ? (prev as Record<string, unknown>)
              : {};
          if (Number(prior.open_action_id) === actionId) return cur;
          return {
            ...cur,
            artifact: {
              ...cur.artifact,
              _studio_apply: {
                ...prior,
                root_menu_id: null,
                open_action_id: actionId,
                host_model: host,
                applied: true,
                via: prior.via || "option_a_promote",
              },
            },
          };
        });
      } catch {
        /* best-effort */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [
    connectionId,
    connection?.url,
    goldOptionA,
    goldPromoted,
    optionAHostLive,
    hostForOpen,
    applyTarget.openActionId,
    setOdooAppUrl,
    setSession,
  ]);
}
