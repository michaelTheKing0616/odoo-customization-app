"use client";

import { useSyncShellContext } from "@/lib/use-sync-shell-context";
import { useStudioDerived } from "./use-studio-derived";
import { useStudioOptionA } from "./use-studio-option-a";
import { useStudioOptionAEffects } from "./use-studio-option-a-effects";
import { useStudioBrief } from "./use-studio-brief";
import { useStudioReview } from "./use-studio-review";
import { useStudioSession } from "./use-studio-session";
import { useStudioState } from "./use-studio-state";

export function useStudioPage(connectionId: string) {
  useSyncShellContext({ route: "app-studio" });
  const s = useStudioState();
  const d = useStudioDerived({
    connectionId,
    session: s.session,
    connection: s.connection,
    goldHost: s.goldHost,
    goldValidationId: s.goldValidationId,
    goldZipBase64: s.goldZipBase64,
    goldPromoted: s.goldPromoted,
    odooAppUrl: s.odooAppUrl,
  });
  const sessionActions = useStudioSession(connectionId, s, d);
  const brief = useStudioBrief(connectionId, s, sessionActions.startOver);
  useStudioOptionAEffects(connectionId, s, d, s.goldPromoted);
  const optionA = useStudioOptionA(connectionId, s, d);
  const review = useStudioReview(connectionId, s, d);

  return {
    connectionId,
    ...s,
    ...d,
    ...sessionActions,
    ...brief,
    ...optionA,
    ...review,
  };
}

export type StudioPageModel = ReturnType<typeof useStudioPage>;
