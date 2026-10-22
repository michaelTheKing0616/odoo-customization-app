/**
 * Touch 101: architectural line drawings instead of blob illustrations. Ink hairlines (an elevation:
 * ground line, piers, voussoirs, dimension ticks) with one cinnabar keystone. "Ingenium", the root of engineer.
 */
export type ArchDrawingKind = "elevation" | "plan";

/** Stones from the springing up, alternating sides (touch 125: onboarding builds the arch). */
const STONES: [number, number][] = [[-90, -60], [60, 90], [-60, -40], [40, 60], [-40, -15], [15, 40]];
function stonePath([a0, a1]: [number, number]) {
  const p = (a: number, r: number) => { const t = (a * Math.PI) / 180; return `${(60 + r * Math.sin(t)).toFixed(2)} ${(40 - r * Math.cos(t)).toFixed(2)}`; };
  return `M${p(a0, 16)}L${p(a0, 30)}A30 30 0 0 1 ${p(a1, 30)}L${p(a1, 16)}A16 16 0 0 0 ${p(a0, 16)}Z`;
}

export function stonesLaid(done: number, total: number): number {
  if (total <= 0) return 0;
  return Math.min(STONES.length, Math.round((Math.max(0, done) / total) * STONES.length));
}

export function ArchDrawing({ kind = "elevation", width = 120, className, progress }: { kind?: ArchDrawingKind; width?: number; className?: string; progress?: { done: number; total: number } }) {
  const laid = progress ? stonesLaid(progress.done, progress.total) : 0;
  const keyIn = !progress || (progress.total > 0 && progress.done >= progress.total);
  const h = Math.round(width * 0.6);
  return (
    <svg viewBox="0 0 120 72" width={width} height={h} aria-hidden className={["arch-drawing", className].filter(Boolean).join(" ")} data-testid="arch-drawing">
      <g fill="none" stroke="var(--ink, #1A1C21)" strokeWidth="0.75" strokeLinecap="round" opacity="0.7">
        <path d="M4 66h112" />
        {kind === "elevation" ? (
          <>
            <path d="M30 66V40a30 30 0 0 1 60 0v26" />
            <path d="M44 66V40a16 16 0 0 1 32 0v26" />
            {[-60, -40, -20, 20, 40, 60].map((a) => {
              const r = (a * Math.PI) / 180;
              const x1 = 60 + 16 * Math.sin(r), y1 = 40 - 16 * Math.cos(r), x2 = 60 + 30 * Math.sin(r), y2 = 40 - 30 * Math.cos(r);
              return <path key={a} d={`M${x1.toFixed(2)} ${y1.toFixed(2)}L${x2.toFixed(2)} ${y2.toFixed(2)}`} />;
            })}
            <path d="M30 70v-2M90 70v-2M30 69h60" strokeDasharray="1.5 1.5" opacity="0.6" />
          </>
        ) : (
          <>
            <rect x="24" y="14" width="72" height="44" />
            <path d="M24 36h72M60 14v44" strokeDasharray="2 2" opacity="0.6" />
            <path d="M48 58a12 12 0 0 1 24 0" />
          </>
        )}
      </g>
      {kind === "elevation" && progress ? STONES.slice(0, laid).map((st, i) => <path key={i} d={stonePath(st)} fill="var(--ink, #1A1C21)" opacity="0.18" className="arch-stone" />) : null}
      {kind === "elevation" && !keyIn ? null : kind === "elevation" ? <path className={progress ? "arch-key-drop" : undefined} d="M55.86 24.55A16 16 0 0 1 64.14 24.55L67.76 11.02A30 30 0 0 0 52.24 11.02Z" fill="#CF4527" /> : <rect x="57" y="11" width="6" height="6" fill="#CF4527" />}
    </svg>
  );
}
