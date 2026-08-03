"use client";

import { useShellOptional } from "@/context/ShellContext";

/** Sync page-local context into the shell Expert provider. */
export function usePageShellContext(patch: {
  model?: string;
  draftSummary?: string;
  viewType?: string;
  triggerType?: string;
}) {
  const shell = useShellOptional();
  const { model, draftSummary, viewType, triggerType } = patch;
  if (!shell) return;
  shell.setUiContext({
    ...(model !== undefined ? { model } : {}),
    ...(draftSummary !== undefined ? { draftSummary } : {}),
    ...(viewType !== undefined ? { viewType } : {}),
    ...(triggerType !== undefined ? { triggerType } : {}),
  });
}
