"use client";

import * as React from "react";

/**
 * Touch 9: the mark draws from its real construction (ingenium-v2 construction.png):
 * extrados R100 and intrados r46 (centre +3u), springing line, baseline, ±15° radial joints;
 * then the stones fill in. Geometry matches directions/A/svg/ingenium-mark-color.svg (viewBox 256).
 * Shown once per browser on first launch; afterwards (and with reduced motion) it is the finished mark.
 */
const LEGS = "M93.53 57.13A100 100 0 0 0 28 151V208H82V148A46 46 0 0 1 106.92 107.11ZM162.47 57.13A100 100 0 0 1 228 151V208H174V148A46 46 0 0 0 149.08 107.11Z";
const KEYSTONE = "M102.12 54.41A100 100 0 0 1 153.88 54.41L140.65 103.77A46 46 0 0 0 115.35 103.77Z";
const SEEN = "ingenium.logo-construction.seen";

export function LogoConstruction({ size = 40, className }: { size?: number; className?: string }) {
  const [draw, setDraw] = React.useState(false);
  React.useEffect(() => {
    try {
      if (!localStorage.getItem(SEEN)) {
        localStorage.setItem(SEEN, "1");
        setDraw(true);
      }
    } catch { /* storage off: show finished mark */ }
  }, []);
  return (
    <svg viewBox="0 0 256 256" width={size} height={size} role="img" aria-label="Ingenium" className={["logo-construction", draw && "is-drawing", className].filter(Boolean).join(" ")} data-testid="logo-construction">
      <g className="lc-lines" fill="none" stroke="var(--accent7, #0f766e)" strokeWidth="1.5" aria-hidden>
        <circle cx="128" cy="151" r="100" pathLength={1} />
        <circle cx="128" cy="148" r="46" pathLength={1} />
        <line x1="0" y1="151" x2="256" y2="151" pathLength={1} />
        <line x1="0" y1="208" x2="256" y2="208" pathLength={1} />
        <line x1="128" y1="151" x2="101.1" y2="50.6" pathLength={1} />
        <line x1="128" y1="151" x2="154.9" y2="50.6" pathLength={1} />
      </g>
      <path className="lc-fill" fill="var(--ink, #1A1C21)" d={LEGS} />
      <path className="lc-fill lc-key" fill="#CF4527" d={KEYSTONE} />
    </svg>
  );
}
