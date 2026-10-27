import contractJson from "./contract.json";

/** Presence clips from the avatar contract. Expert also has listening and speaking. */
export const BOT_STATES = [
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
  "listening",
  "speaking",
] as const;

export type BotState = (typeof BOT_STATES)[number];

export const BOT_ROLES = [
  "chief_of_staff",
  "configurator",
  "studio",
  "access",
  "data",
  "doctor",
  "auditor",
  "scribe",
  "release",
  "front_desk",
  "consultant",
  "ops",
  "specialist",
  "expert",
] as const;

export type BotRole = (typeof BOT_ROLES)[number];

type AvatarRecord = {
  display: string;
  file: string;
  clips: string[];
  accent: string;
  loop: string[];
  once: string[];
};

const avatars = contractJson.avatars as Record<BotRole, AvatarRecord>;

const STATE_LABEL: Record<BotState, string> = {
  idle: "ready",
  acknowledged: "acknowledged",
  thinking: "thinking",
  working: "working",
  waiting_user: "waiting for you",
  waiting_approval: "waiting for approval",
  blocked: "blocked",
  applying: "applying",
  verifying: "checking",
  done: "done",
  listening: "listening",
  speaking: "speaking",
};

export function isBotRole(value: string): value is BotRole {
  return (BOT_ROLES as readonly string[]).includes(value);
}

export function avatarRecord(role: BotRole): AvatarRecord {
  return avatars[role];
}

export function displayName(role: BotRole): string {
  return avatars[role].display;
}

export function stateLabel(state: BotState): string {
  return STATE_LABEL[state];
}

export function previewSrc(role: BotRole, theme: "light" | "navy"): string {
  return `/avatars/ingenium/${role}_${theme}.png`;
}

export function glbSrc(role: BotRole): string {
  return `/avatars/ingenium/${avatars[role].file}`;
}

/** Clip to play, and whether the contract loops it. Unknown states fall back to idle. */
export function resolveClip(role: BotRole, state: BotState): { clip: string; loop: boolean } {
  const record = avatars[role];
  const clip = record.clips.includes(state) ? state : "idle";
  return { clip, loop: record.loop.includes(clip) };
}

export function accentColor(role: BotRole, override?: string): string {
  if (role === "specialist" && override && /^#[0-9A-Fa-f]{6}$/.test(override)) return override;
  return avatars[role].accent;
}

/** Browsers drop the oldest WebGL context after about 16. Stay under that so a lost context never blanks a face. */
const GL_BUDGET = 12;
let glInUse = 0;

export function acquireAvatarGl(): boolean {
  if (glInUse >= GL_BUDGET) return false;
  glInUse += 1;
  return true;
}

export function releaseAvatarGl(): void {
  glInUse = Math.max(0, glInUse - 1);
}

export type MorphWeights = {
  blink: number;
  browUp: number;
  browDown: number;
  smile: number;
  mouthOpen: number;
};

/** Expert face weights after the clip has posed the mesh. Other roles stay at zero. */
export function expertMorphWeights(
  role: BotRole,
  state: BotState,
  ttsAmplitude: number,
  blink: number,
): MorphWeights {
  const quiet: MorphWeights = { blink: 0, browUp: 0, browDown: 0, smile: 0, mouthOpen: 0 };
  if (role !== "expert") return quiet;
  const mouth = Math.min(1, Math.max(0, ttsAmplitude));
  let browUp = 0;
  let browDown = 0;
  let smile = 0;
  if (state === "thinking" || state === "listening") browUp = 0.55;
  if (state === "blocked") browDown = 0.7;
  if (state === "done") smile = 0.55;
  if (state === "speaking") smile = 0.2;
  return { blink, browUp, browDown, smile, mouthOpen: mouth };
}
