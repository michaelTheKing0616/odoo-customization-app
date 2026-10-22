"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { api } from "@/lib/api";
import type { WireframeMap } from "@/lib/api/wireframe";
import { stashPromptForStudio } from "@/lib/studio-session";

/** Build the plain brief App Studio receives; App Studio then runs all its usual checks. */
export function briefFromMap(m: WireframeMap, answers: Record<string, string>): string {
  const extend = answers.model === "extend" && m.target.maybe ? m.target.maybe : m.target.action === "extend" ? m.target : null;
  const lines: string[] = [];
  lines.push(extend ? `Add to Odoo\u2019s ${extend.name} (${extend.model}).` : `Make a new app called \u201c${m.target.name}\u201d.`);
  const reuse: string[] = [];
  const add: string[] = [];
  for (const r of m.rows) {
    const a = answers[`field:${r.region}`];
    const label = answers[`label:${r.region}`] || r.label;
    if (!label) continue;
    if (r.action === "reuse") reuse.push(`${label} \u2192 ${r.field_label ?? r.field}`);
    else if (a?.startsWith("reuse:")) reuse.push(`${label} \u2192 ${a.slice(6)}`);
    else add.push(`${label} (${r.type ?? "text"})`);
  }
  if (reuse.length) lines.push(`Use the fields Odoo already has: ${reuse.join("; ")}.`);
  if (add.length) lines.push(`Add new fields: ${add.join("; ")}.`);
  lines.push(`Lay the form out like the sketch, in this order: ${m.rows.map((r) => answers[`label:${r.region}`] || r.label).filter(Boolean).join(", ")}.`);
  lines.push(m.install.mode === "data" ? "Ship it as a data module (Odoo Online)." : "Ship it as a custom module.");
  return lines.join(" ");
}

export function StockMapPanel({
  connectionId,
  sketch,
  imageUrl,
  onBuild,
}: {
  connectionId: string;
  sketch: Record<string, unknown>;
  imageUrl: string | null;
  /** Navigation hook (tests); defaults to opening App Studio. */
  onBuild?: (href: string) => void;
}) {
  const [map, setMap] = useState<WireframeMap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [hover, setHover] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setMap(null);
    setError(null);
    api
      .wireframeMap(connectionId, sketch)
      .then((m) => live && setMap(m))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [connectionId, sketch]);

  if (error) return <p className="mt-4 text-sm text-danger" role="alert">We couldn\u2019t match the sketch to this database: {error}</p>;
  if (!map) return <p className="mt-4 text-sm text-muted" role="status">Matching the sketch to fields Odoo already has\u2026</p>;

  const openQuestions = map.questions.filter((q) => !answers[q.id]);
  const send = () => {
    stashPromptForStudio(connectionId, briefFromMap(map, answers));
    const href = `/connections/${connectionId}/studio`;
    if (onBuild) onBuild(href);
    else window.location.assign(href);
  };

  return (
    <section className="mt-4 grid gap-4 md:grid-cols-2" data-testid="wireframe-map">
      {imageUrl ? (
        <figure className="hairline rounded-md p-2">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <div className="relative">
            <img src={imageUrl} alt="Your sketch" className="w-full rounded" />
            {map.rows.map((r) =>
              r.box ? (
                <span
                  key={r.region}
                  aria-hidden
                  data-testid={`wireframe-box-${r.region}`}
                  className={`pointer-events-none absolute rounded-sm border ${hover === r.region ? "border-2 border-accent bg-accent/10" : "border-dashed border-accent/40"}`}
                  style={{ left: `${r.box[0] * 100}%`, top: `${r.box[1] * 100}%`, width: `${r.box[2] * 100}%`, height: `${r.box[3] * 100}%` }}
                />
              ) : null,
            )}
          </div>
          <figcaption className="mt-1 text-xs text-muted">{hover ? `Box ${hover}` : "Hover a row to see its box"}</figcaption>
        </figure>
      ) : null}
      <div className="space-y-3">
        <p className="text-sm text-ink" data-testid="wireframe-map-summary">
          {map.target.action === "extend" ? `Adds to Odoo\u2019s ${map.target.name}. ` : `A new app: ${map.target.name}. `}
          {map.summary}
        </p>
        <p className="text-xs text-muted">{map.install.why}</p>
        {map.guards.flagged_regions.length ? (
          <p className="text-xs text-warning" data-testid="wireframe-map-flagged">
            {map.guards.flagged_regions.length} box(es) contained instructions instead of a label, so we ignored their text.
          </p>
        ) : null}
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-muted">
              <th className="py-1">On the sketch</th>
              <th className="py-1">In Odoo</th>
            </tr>
          </thead>
          <tbody>
            {map.rows.map((r) => (
              <tr
                key={r.region}
                onMouseEnter={() => setHover(r.region)}
                onMouseLeave={() => setHover(null)}
                data-list-row
                className={hover === r.region ? "bg-accent-subtle" : undefined}
              >
                <td className="py-1">{answers[`label:${r.region}`] || r.label || <em className="text-muted">Unreadable</em>}</td>
                <td className="py-1">
                  {r.action === "reuse" ? (
                    <>
                      Uses <strong>{r.field_label}</strong> <span className="font-mono text-xs text-muted">{r.field}</span>
                    </>
                  ) : (
                    <span className="text-muted">New field ({r.type})</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {openQuestions.length ? (
          <div className="space-y-2" data-testid="wireframe-map-questions">
            {openQuestions.map((q) => (
              <div key={q.id} className="hairline rounded-md p-3">
                <p className="text-sm text-ink">{q.text}</p>
                {q.options.length ? (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {q.options.map((o) => (
                      <Button key={o.id} size="sm" variant="secondary" onClick={() => setAnswers((a) => ({ ...a, [q.id]: o.id }))}>
                        {o.label}
                      </Button>
                    ))}
                  </div>
                ) : (
                  <input
                    className="mt-2 w-full rounded border border-border bg-background px-2 py-1 text-sm"
                    placeholder="Name for this box"
                    onKeyDown={(e) => {
                      const v = (e.target as HTMLInputElement).value.trim();
                      if (e.key === "Enter" && v) setAnswers((a) => ({ ...a, [q.id]: v }));
                    }}
                  />
                )}
              </div>
            ))}
          </div>
        ) : null}
        <Button variant="primary" disabled={openQuestions.length > 0} onClick={send} data-testid="wireframe-map-build">
          {openQuestions.length ? `Answer ${openQuestions.length} question${openQuestions.length > 1 ? "s" : ""} first` : "Build it in App Studio"}
        </Button>
        <p className="text-xs text-muted">App Studio checks it against this database and shows a preview before anything is written.</p>
      </div>
    </section>
  );
}
