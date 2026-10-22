"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { GuardOut } from "@/lib/api/view-engine-2b";
import { editorIdentity } from "@/lib/viewDesigner2b";
import type { ViewDesignerState } from "./useViewDesigner";

const PRESENCE_EVERY_MS = 20000;

/** Stage 2b state around the designer: who else is here, and the upgrade check on open. */
export function useDesigner2b(s: ViewDesignerState, connectionId: string) {
  const [others, setOthers] = useState<string[]>([]);
  const [guard, setGuard] = useState<GuardOut | null>(null);

  useEffect(() => {
    const me = editorIdentity();
    const screen = { model: s.model, view_type: s.viewType, view_id: s.viewId };
    let live = true;
    const ping = () =>
      api
        .presence(connectionId, screen, me.id, me.name)
        .then((o) => live && setOthers(o.others.map((x) => x.name)))
        .catch(() => undefined);
    void ping();
    const t = window.setInterval(ping, PRESENCE_EVERY_MS);
    return () => {
      live = false;
      window.clearInterval(t);
      void api.presence(connectionId, screen, me.id, me.name, true).catch(() => undefined);
    };
  }, [connectionId, s.model, s.viewType, s.viewId]);

  const layerActive = Boolean(s.base?.layer?.active);
  useEffect(() => {
    setGuard(null);
    if (!layerActive) return;
    let live = true;
    api
      .guardCheck(connectionId, { model: s.model, view_type: s.viewType, view_id: s.viewId })
      .then((g) => live && setGuard(g))
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [connectionId, s.model, s.viewType, s.viewId, layerActive, s.publishCount]);

  return { others, guard };
}
