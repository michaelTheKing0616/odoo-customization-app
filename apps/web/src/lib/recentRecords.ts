/** Touch 143: recent records kept on this device, so Find anything shows them instantly, even offline. */
export type RecentRecord = { model: string; id: number; name: string; at: number };
const key = (c: string) => `ingenium.recent-records.${c}`;

export function readRecent(connectionId: string): RecentRecord[] {
  try { return JSON.parse(localStorage.getItem(key(connectionId)) ?? "[]") as RecentRecord[]; } catch { return []; }
}

export function pushRecent(connectionId: string, r: Omit<RecentRecord, "at">, max = 20): RecentRecord[] {
  const next = [{ ...r, at: Date.now() }, ...readRecent(connectionId).filter((x) => !(x.model === r.model && x.id === r.id))].slice(0, max);
  try { localStorage.setItem(key(connectionId), JSON.stringify(next)); } catch { /* ignore */ }
  return next;
}
