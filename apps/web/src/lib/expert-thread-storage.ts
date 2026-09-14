import type { ExpertAskResponse } from "@/lib/api";

export type ExpertTurn = {
  role: "user" | "assistant";
  content: string;
  response?: ExpertAskResponse;
};

export function expertThreadStorageKey(connectionId: string): string {
  return `expert-thread-${connectionId}`;
}

export function loadExpertThread(connectionId: string): ExpertTurn[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = sessionStorage.getItem(expertThreadStorageKey(connectionId));
    return raw ? (JSON.parse(raw) as ExpertTurn[]) : [];
  } catch {
    return [];
  }
}

export function saveExpertThread(connectionId: string, turns: ExpertTurn[]): void {
  sessionStorage.setItem(expertThreadStorageKey(connectionId), JSON.stringify(turns));
}

export function clearExpertThread(connectionId: string): void {
  sessionStorage.removeItem(expertThreadStorageKey(connectionId));
}
