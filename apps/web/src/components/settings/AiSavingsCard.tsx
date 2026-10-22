"use client";

import { useEffect, useState } from "react";
import { request } from "@/lib/api/client";

export type AiCacheStats = {
  calls: number;
  hits_exact: number;
  hits_semantic: number;
  hit_rate: number;
  tokens_saved: number;
  usd_saved: number;
  usd_spent_est: number;
  context_cache_hits: number;
  model_fallbacks: number;
  live_entries: number;
  guard_flags: Record<string, number>;
};

const usd = (n: number) =>
  n >= 1 ? `$${n.toFixed(2)}` : n > 0 ? `$${n.toFixed(4)}` : "$0.00";
const num = (n: number) => new Intl.NumberFormat("en-NG").format(Math.round(n));

/** Arch gauge: the hit rate fills the arch's voussoirs left to right. */
function ArchGauge({ rate }: { rate: number }) {
  const stones = 9;
  const filled = Math.round(Math.max(0, Math.min(1, rate)) * stones);
  return (
    <svg viewBox="0 0 120 66" className="ai-arch" role="img" aria-label={`Cache hit rate ${Math.round(rate * 100)}%`}>
      {Array.from({ length: stones }, (_, i) => {
        const a0 = Math.PI - (i / stones) * Math.PI;
        const a1 = Math.PI - ((i + 1) / stones) * Math.PI;
        const gap = 0.025;
        const pt = (a: number, r: number) => `${60 + r * Math.cos(a)},${62 - r * Math.sin(a)}`;
        const d = `M${pt(a0 - gap, 56)} A56,56 0 0 1 ${pt(a1 + gap, 56)} L${pt(a1 + gap, 38)} A38,38 0 0 0 ${pt(a0 - gap, 38)} Z`;
        return <path key={i} d={d} className={i < filled ? "ai-arch-on" : "ai-arch-off"} />;
      })}
    </svg>
  );
}

export function AiSavingsCard() {
  const [s, setS] = useState<AiCacheStats | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    request<AiCacheStats>("/api/ai/cache/stats")
      .then((d) => live && setS(d))
      .catch(() => live && setErr("AI usage isn't available right now."));
    return () => {
      live = false;
    };
  }, []);

  const flags = s ? Object.values(s.guard_flags || {}).reduce((a, b) => a + b, 0) : 0;
  const hits = s ? s.hits_exact + s.hits_semantic : 0;

  return (
    <section className="stg-panel ai-savings" data-testid="settings-ai-savings" aria-busy={!s && !err}>
      <div className="ai-savings-head">
        <div>
          <h2 className="stg-panel-title">AI spend and savings</h2>
          <p className="stg-panel-sub">Repeated questions are answered from the cache, at no cost.</p>
        </div>
        {s ? <ArchGauge rate={s.hit_rate} /> : null}
      </div>
      {err ? <p className="ai-savings-note" role="status">{err}</p> : null}
      {!s && !err ? <div className="ai-savings-skel" aria-hidden /> : null}
      {s ? (
        <dl className="ai-savings-grid">
          <div>
            <dt>Saved</dt>
            <dd className="ai-num ai-num-lead">{usd(s.usd_saved)}</dd>
          </div>
          <div>
            <dt>Spent</dt>
            <dd className="ai-num">{usd(s.usd_spent_est)}</dd>
          </div>
          <div>
            <dt>Answered from cache</dt>
            <dd className="ai-num">
              {Math.round(s.hit_rate * 100)}% <span className="ai-sub">({num(hits)} of {num(s.calls)})</span>
            </dd>
          </div>
          <div>
            <dt>Tokens saved</dt>
            <dd className="ai-num">{num(s.tokens_saved)}</dd>
          </div>
          <div>
            <dt>Backup model used</dt>
            <dd className="ai-num">{num(s.model_fallbacks)}×</dd>
          </div>
          <div>
            <dt>Safety checks triggered</dt>
            <dd className="ai-num">{num(flags)}</dd>
          </div>
        </dl>
      ) : null}
    </section>
  );
}
