"use client";

/** Touch 58: a record's journey as a transit map. Each system is a line, each step a station. */
export type TraceEvent = { at: number; step: string; status: string; detail: string };
export type Line = "app" | "ingenium" | "odoo";

export function lineFor(step: string): Line {
  const s = step.toLowerCase();
  if (/(push|write|create|odoo|post|invoice|confirm)/.test(s)) return "odoo";
  if (/(receive|webhook|fetch|pull|poll|source)/.test(s)) return "app";
  return "ingenium";
}

const Y: Record<Line, number> = { app: 20, ingenium: 50, odoo: 80 };

export function TransitMap({ events, appName }: { events: TraceEvent[]; appName: string }) {
  if (!events.length) return null;
  const step = 90;
  const w = Math.max(240, 60 + (events.length - 1) * step + 60);
  const pts = events.map((e, i) => ({ e, x: 60 + i * step, y: Y[lineFor(e.step)] }));
  const d = pts.map((p, i) => (i ? `L${p.x} ${p.y}` : `M${p.x} ${p.y}`)).join(" ");
  const label: Record<Line, string> = { app: appName, ingenium: "Ingenium", odoo: "Odoo" };
  return (
    <figure className="transit-map" data-testid="transit-map">
      <svg viewBox={`0 0 ${w} 120`} width="100%" role="img" aria-label={`Journey: ${events.map((e) => `${e.step} (${e.status})`).join(", then ")}`}>
        {(Object.keys(Y) as Line[]).map((l) => (
          <g key={l} aria-hidden>
            <line x1="0" x2={w} y1={Y[l]} y2={Y[l]} className={`tm-rail tm-${l}`} />
            <text x="4" y={Y[l] - 6} className="tm-line-label">{label[l]}</text>
          </g>
        ))}
        <path d={d} className="tm-route" fill="none" />
        {pts.map((p, i) => (
          <g key={i}>
            <circle cx={p.x} cy={p.y} r="6" className="tm-station" data-status={p.e.status} />
            <text x={p.x} y={p.y + 20} textAnchor="middle" className="tm-station-label">{p.e.step}</text>
          </g>
        ))}
      </svg>
      <figcaption className="sr-only">{events.map((e) => `${new Date(e.at * 1000).toLocaleString()}: ${e.step}, ${e.status}${e.detail ? `, ${e.detail}` : ""}`).join(". ")}</figcaption>
    </figure>
  );
}
