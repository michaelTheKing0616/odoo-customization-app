/**
 * Stone sound set (design touches 50-53). Off by default; opt-in per browser.
 * Routine actions stay silent: only lock-in, error, approval and the sound logo exist.
 * Muted while presenting (html[data-presenting]) and when no file is shipped yet.
 */
export type SoundName = "lock-in" | "toggle" | "error" | "approval" | "logo";

export const SOUND_STORAGE_KEY = "ingenium.sound";
const FILES: Record<SoundName, string> = {
  "lock-in": "/sounds/stone-lock-in.mp3",
  toggle: "/sounds/stone-toggle.mp3",
  error: "/sounds/stone-error.mp3",
  approval: "/sounds/stone-approval.mp3",
  logo: "/sounds/sound-logo.mp3",
};

export function soundEnabled(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(SOUND_STORAGE_KEY) === "on";
  } catch {
    return false;
  }
}

export function setSoundEnabled(on: boolean): void {
  try {
    window.localStorage.setItem(SOUND_STORAGE_KEY, on ? "on" : "off");
  } catch {
    /* storage blocked: stays off */
  }
}

export function soundMuted(): boolean {
  if (typeof document === "undefined") return true;
  return document.documentElement.hasAttribute("data-presenting") || document.hidden;
}

export function playSound(name: SoundName): void {
  if (!soundEnabled() || soundMuted()) return;
  try {
    const vol = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--sound-volume")) || 0.35;
    const a = new Audio(FILES[name]);
    a.volume = Math.min(1, Math.max(0, vol));
    void a.play().catch(() => undefined);
  } catch {
    /* no audio support */
  }
}
