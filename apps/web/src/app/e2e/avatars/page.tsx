"use client";

import { BotAvatar, BotPresenceChip } from "@/components/avatars/BotAvatar";
import { BOT_ROLES, BOT_STATES, displayName, type BotState } from "@/lib/avatars/playback";

const PRESENCE: BotState[] = [
  "idle",
  "acknowledged",
  "thinking",
  "working",
  "waiting_user",
  "waiting_approval",
  "blocked",
  "applying",
  "verifying",
  "done",
];

/** Example gallery for the 14 Ingenium Bot avatars. Not a live roster. */
export default function AvatarGalleryPage() {
  return (
    <main className="space-y-8 bg-surface p-6 text-ink">
      <header className="space-y-1">
        <p className="text-xs text-muted">Example</p>
        <h1 className="text-lg font-medium">Ingenium Bot avatars</h1>
      </header>
      <section className="space-y-2" aria-label="Expert states">
        <h2 className="text-sm font-medium">Expert</h2>
        <div className="flex flex-wrap gap-3">
          {BOT_STATES.map((state) => (
            <div key={state} className="flex flex-col items-center gap-1">
              <BotAvatar role="expert" state={state} size={72} ttsAmplitude={state === "speaking" ? 0.6 : 0} />
              <span className="text-xs text-muted">{state}</span>
            </div>
          ))}
        </div>
      </section>
      <ul className="flex flex-wrap gap-4" data-testid="avatar-gallery">
        {BOT_ROLES.map((role) => (
          <li key={role} className="flex w-32 flex-col items-center gap-2 text-center">
            <BotAvatar role={role} state="idle" size={96} />
            <span className="text-xs">{displayName(role)}</span>
          </li>
        ))}
      </ul>
      <section className="space-y-2" aria-label="Example presence">
        <h2 className="text-sm font-medium">Presence</h2>
        <div className="flex flex-wrap gap-2">
          {PRESENCE.map((state) => (
            <BotPresenceChip key={state} role="expert" state={state} />
          ))}
        </div>
      </section>
    </main>
  );
}
