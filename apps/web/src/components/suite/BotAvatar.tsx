"use client";

import type { CSSProperties } from "react";
import { BotAvatar as IngeniumBotAvatar } from "@/components/avatars/BotAvatar";
import type { BotState as IngeniumBotState } from "@/lib/avatars/playback";
import { KEYSTONE_ARCH, KEYSTONE_BADGES, KEYSTONE_GLYPHS, KEYSTONE_STONE, type KeystoneBot } from "@/components/ui/icons";
import styles from "./BotAvatar.module.css";

/** Ingenium bots (SPEC 20.2). Each is the Keystone arch with its own sign in the opening. */
export type Bot = KeystoneBot;
/** Touch 104: one live state machine. idle → thinking → working → done, or needs_you at any point. */
export type BotState = "idle" | "thinking" | "working" | "done" | "needs_you";
export const BOT_NAMES: Record<Bot, string> = {
  expert: "Ingenium Expert", ask: "Ask", builder: "Builder", inspector: "Inspector", runner: "Runner", guard: "Money guard",
};
/** Touch 113: one-line specialty per bot; all speak in the same calm voice. */
export const BOT_SPECIALTY: Record<Bot, string> = {
  expert: "Answers Odoo questions and suggests fixes",
  ask: "Finds answers in your database",
  builder: "Drafts apps, fields and screens",
  inspector: "Checks changes before they go live",
  runner: "Runs approved plans and scripts",
  guard: "Stops risky money and delete actions",
};
const STATE_WORDS: Record<BotState, string> = { idle: "ready", thinking: "thinking", working: "working", done: "done", needs_you: "needs you" };

const NEXT: Record<BotState, BotState[]> = { idle: ["thinking", "needs_you"], thinking: ["working", "done", "needs_you", "idle"], working: ["done", "needs_you", "idle"], done: ["idle", "thinking"], needs_you: ["thinking", "idle"] };
/** Allowed moves; anything else snaps through idle so the avatar never shows an impossible jump. */
export function canMove(from: BotState, to: BotState): boolean { return from === to || NEXT[from].includes(to); }

const GLYPH = KEYSTONE_GLYPHS;

const SUITE_PRESENCE: Record<BotState, IngeniumBotState> = {
  idle: "idle",
  thinking: "thinking",
  working: "working",
  done: "done",
  needs_you: "waiting_user",
};

export function BotAvatar({ bot, state = "idle", size = 24, showState = true }: { bot: Bot; state?: BotState; size?: 16 | 20 | 24 | 32 | 48; showState?: boolean }) {
  if (bot === "expert") {
    return <IngeniumBotAvatar role="expert" state={SUITE_PRESENCE[state]} size={size} />;
  }
  const label = `${BOT_NAMES[bot]}: ${STATE_WORDS[state]}`;
  const title = `${label}. ${BOT_SPECIALTY[bot]}.`;
  return (
    <span className={styles.avatar} data-state={state} data-bot={bot} style={{ "--ks-size": `${size}px` } as CSSProperties} role="img" aria-label={label} title={title}>
      <svg viewBox="0 0 256 256" aria-hidden focusable="false">
        {/* Touch 7: bots sit in an arch-shaped tile; people stay round. */}
        <path className={styles.tile} d="M0 256V128a128 128 0 0 1 256 0v128z" />
        <g transform="translate(29.7 23.16) scale(0.768)">
          <path className={styles.arch} d={KEYSTONE_ARCH} />
          {state === "working" ? <path className={styles.archFill} d={KEYSTONE_ARCH} /> : null}
          <path className={styles.keystone} d={KEYSTONE_STONE} />
          {size >= 20 ? (
            <>
              {GLYPH[bot].paths.map((d) => <path key={d} className={styles.glyph} d={d} />)}
              {(GLYPH[bot].circles ?? []).map((c) => <circle key={`${c.cx}-${c.cy}`} className={styles.glyph} cx={c.cx} cy={c.cy} r={c.r} />)}
            </>
          ) : null}
        </g>
      </svg>
      {showState && state !== "idle" && size >= 20 ? <span className={styles.badge} aria-hidden><svg viewBox="0 0 24 24"><path d={KEYSTONE_BADGES[state === "working" ? "thinking" : state]} /></svg></span> : null}
    </span>
  );
}
