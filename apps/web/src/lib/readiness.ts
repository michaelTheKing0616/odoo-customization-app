/**
 * Touch 128: power features are introduced once the person shows they're ready, not on day one.
 * Nothing is hidden; each feature just gets one quiet introduction at the right moment.
 * Shortcuts are already coached after repeated mouse use (coachShortcut).
 */
const KEY = "ingenium.readiness.v1";

export type Intro = { id: "density" | "code-runner"; message: string; href: (connectionId: string | null) => string | null };

export const INTROS: { afterDays: number; intro: Intro }[] = [
  { afterDays: 3, intro: { id: "density", message: "You're finding your way around. You can make screens denser in Settings.", href: () => "/settings" } },
  { afterDays: 6, intro: { id: "code-runner", message: "For one-off checks, the Code Runner runs safe read-only scripts against this database.", href: (c) => (c ? `/connections/${c}/code-runner` : null) } },
];

type State = { days: string[]; shown: string[] };

export function recordDay(state: State, today: string): State {
  return state.days.includes(today) ? state : { ...state, days: [...state.days, today].slice(-30) };
}

export function dueIntro(state: State): Intro | null {
  for (const { afterDays, intro } of INTROS) {
    if (state.days.length >= afterDays && !state.shown.includes(intro.id)) return intro;
  }
  return null;
}

/** Records today as an active day and returns at most one introduction that is due (marking it shown). */
export function takeIntro(today = new Date().toISOString().slice(0, 10)): Intro | null {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "null") as State | null;
    let st = recordDay(raw ?? { days: [], shown: [] }, today);
    const intro = dueIntro(st);
    if (intro) st = { ...st, shown: [...st.shown, intro.id] };
    localStorage.setItem(KEY, JSON.stringify(st));
    return intro;
  } catch {
    return null;
  }
}
