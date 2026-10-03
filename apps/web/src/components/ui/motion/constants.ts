/**
 * The only module that defines motion durations and easings (UI-F09).
 * Copied from T7_UI_MOTION_COPY / 13_UI_SCREEN_SPECS. Do not invent new numbers.
 */

export const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/** Cap from the spec: reduced motion is opacity only at this duration or less. */
export const REDUCED_MOTION_MAX_MS = 200;

export const EXIT_RATIO = 0.75;

export const PRESS_SCALE = 0.97;

export const MOTION_PROPERTIES = ["transform", "opacity"] as const;

export const DURATION_RANGE = {
  pressMs: { min: 100, max: 160 },
  dropdownMs: { min: 150, max: 250 },
  modalMs: { min: 200, max: 300 },
  staggerMs: { min: 30, max: 80 },
} as const;

export const EASE_ENTER_EXIT = {
  css: "cubic-bezier(0.23, 1, 0.32, 1)",
  bezier: [0.23, 1, 0.32, 1] as const,
};

export const EASE_DRAWER = {
  css: "cubic-bezier(0.32, 0.72, 0, 1)",
  bezier: [0.32, 0.72, 0, 1] as const,
};

export const DURATION = {
  pressMs: 130,
  dropdownMs: 200,
  modalMs: 250,
  drawerMs: 280,
  staggerMs: 50,
  reducedMotionMs: REDUCED_MOTION_MAX_MS,
  rowHoverMs: 80,
  saveConfirmMs: 150,
} as const;

export function exitDurationMs(enterMs: number): number {
  return Math.round(enterMs * EXIT_RATIO);
}

export function seconds(ms: number): number {
  return ms / 1000;
}
