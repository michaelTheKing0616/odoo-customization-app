"use client";

import { useSyncExternalStore } from "react";
import { REDUCED_MOTION_QUERY } from "./constants";
import { readPrefersReducedMotion } from "./resolve";

function subscribe(onChange: () => void) {
  const media = window.matchMedia(REDUCED_MOTION_QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, readPrefersReducedMotion, () => false);
}
