import type { Transition } from "motion/react";
import {
  DURATION,
  EASE_DRAWER,
  EASE_ENTER_EXIT,
  REDUCED_MOTION_QUERY,
  exitDurationMs,
  seconds,
} from "./constants";

export type MotionSide = "left" | "right";

export type PanelMotionStyle = {
  opacity: number;
  x?: string | number;
  y?: string | number;
  scale?: number;
};

/**
 * Same motion node stays mounted. Only `animate` changes, so a close mid-open
 * tweens from the in-progress value (Motion's default interruptible behavior).
 */
export const DRAWER_INTERRUPTIBLE = {
  remountOnToggle: false,
  resetInitialOnClose: false,
} as const;

export function readPrefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia(REDUCED_MOTION_QUERY).matches;
}

export function drawerClosedTarget(side: MotionSide): PanelMotionStyle {
  return { x: side === "right" ? "100%" : "-100%", opacity: 0 };
}

export function drawerOpenTarget(): PanelMotionStyle {
  return { x: 0, opacity: 1 };
}

export function drawerAnimateForOpen(open: boolean, side: MotionSide): PanelMotionStyle {
  return open ? drawerOpenTarget() : drawerClosedTarget(side);
}

/** Drop transform/scale when reduced motion is on. Opacity remains. */
export function resolveMotionStyle(
  full: PanelMotionStyle,
  reduced: boolean,
): PanelMotionStyle {
  if (!reduced) return full;
  return { opacity: full.opacity };
}

export function resolvePanelAnimate(
  open: boolean,
  side: MotionSide,
  reduced: boolean,
): PanelMotionStyle {
  const full = drawerAnimateForOpen(open, side);
  if (!reduced) return full;
  // x: 0 cancels a slide from the first paint. It is not a travel animation.
  return { opacity: full.opacity, x: 0 };
}

export function backdropAnimate(open: boolean): PanelMotionStyle {
  return { opacity: open ? 1 : 0 };
}

export function panelTransition(open: boolean, reduced: boolean): Transition {
  const enterMs = DURATION.drawerMs;
  const ms = reduced ? DURATION.reducedMotionMs : open ? enterMs : exitDurationMs(enterMs);
  return {
    type: "tween",
    duration: seconds(ms),
    ease: reduced ? [...EASE_ENTER_EXIT.bezier] : [...EASE_DRAWER.bezier],
  };
}

export function listItemTransition(
  index: number,
  stagger: boolean,
  reduced: boolean,
): Transition {
  const ms = reduced ? DURATION.reducedMotionMs : DURATION.dropdownMs;
  const delayMs = stagger && !reduced ? index * DURATION.staggerMs : 0;
  return {
    type: "tween",
    duration: seconds(ms),
    delay: seconds(delayMs),
    ease: [...EASE_ENTER_EXIT.bezier],
  };
}

export function listItemInitial(reduced: boolean): PanelMotionStyle {
  return resolveMotionStyle({ opacity: 0, y: 8 }, reduced);
}

export function listItemRest(reduced: boolean): PanelMotionStyle {
  return resolveMotionStyle({ opacity: 1, y: 0 }, reduced);
}

export function motionKeys(style: object): string[] {
  return Object.keys(style);
}
