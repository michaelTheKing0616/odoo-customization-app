"use client";

import { useEffect } from "react";
import { useShellOptional } from "@/context/ShellContext";

export function useSyncShellContext(patch: {
  route?: string;
  model?: string;
  field?: string;
  resId?: number;
  draftSummary?: string;
  viewType?: string;
  triggerType?: string;
}) {
  const setUiContext = useShellOptional()?.setUiContext;
  const { route, model, field, resId, draftSummary, viewType, triggerType } = patch;

  useEffect(() => {
    if (!setUiContext) return;
    setUiContext({ route, model, field, resId, draftSummary, viewType, triggerType });
  }, [setUiContext, route, model, field, resId, draftSummary, viewType, triggerType]);
}
