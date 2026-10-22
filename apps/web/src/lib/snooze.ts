/** Q2 touch 159: snooze is a personal view setting, kept on this device. It never changes the approval. */
const KEY = "ingenium.snooze";

export type SnoozeMap = Record<string, number>;

export function readSnoozes(now = Date.now()): SnoozeMap {
  try {
    const all = JSON.parse(localStorage.getItem(KEY) ?? "{}") as SnoozeMap;
    return Object.fromEntries(Object.entries(all).filter(([, until]) => until > now));
  } catch {
    return {};
  }
}

export function writeSnoozes(m: SnoozeMap) {
  try {
    localStorage.setItem(KEY, JSON.stringify(m));
  } catch {
    /* private mode: snooze just won't stick */
  }
}

/** Next 08:00 in Lagos (UTC+1) strictly after now. */
export function tomorrowMorningLagos(now = Date.now()): number {
  const lagos = new Date(now + 3_600_000);
  const t = Date.UTC(lagos.getUTCFullYear(), lagos.getUTCMonth(), lagos.getUTCDate(), 8) - 3_600_000;
  return t > now ? t : t + 86_400_000;
}

export function untilLabel(t: number): string {
  return new Date(t).toLocaleString("en-GB", { timeZone: "Africa/Lagos", weekday: "short", hour: "2-digit", minute: "2-digit" }) + " WAT";
}
