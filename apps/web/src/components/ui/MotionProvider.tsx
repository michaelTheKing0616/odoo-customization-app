"use client";

import type { ReactNode } from "react";

type MotionProviderProps = {
  children: ReactNode;
};

/**
 * Placeholder for Motion (motion/react) feature bundles.
 * Reduced motion is handled by CSS (`motion-safe:` utilities and `prefers-reduced-motion`
 * rules in globals.css), not by toggling JS animation off here.
 */
export function MotionProvider({ children }: MotionProviderProps) {
  return children;
}
