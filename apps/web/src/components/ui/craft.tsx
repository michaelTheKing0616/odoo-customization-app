"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { request } from "@/lib/api/client";

/** 19: keycap, Cmd/Ctrl by platform. Write "Mod" for the platform key. */
export function Keycap({ keys }: { keys: string }) {
  const [mac, setMac] = React.useState(true);
  React.useEffect(() => setMac(/mac|iphone|ipad/i.test(navigator.platform || navigator.userAgent)), []);
  return (
    <span className="inline-flex gap-1" aria-label={keys.replace("Mod", mac ? "Command" : "Control")}>
      {keys.split("+").map((k) => (
        <kbd key={k} className="keycap">
          {k === "Mod" ? (mac ? "⌘" : "Ctrl") : k}
        </kbd>
      ))}
    </span>
  );
}

const LAGOS = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Africa/Lagos",
  dateStyle: "medium",
  timeStyle: "short",
});

export function relativeLabel(ms: number, now: number): string {
  const s = Math.round((now - ms) / 1000);
  if (s < 45) return "just now";
  const m = Math.round(s / 60);
  if (m < 60) return `${m}\u00a0min ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}\u00a0h ago`;
  const d = Math.round(h / 24);
  return `${d}\u00a0day${d === 1 ? "" : "s"} ago`;
}

/** 21: live relative time, exact Lagos time on hover. */
export function RelativeTime({ value }: { value: string | number | Date }) {
  const ms = new Date(value).getTime();
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, []);
  if (Number.isNaN(ms)) return null;
  return (
    <time dateTime={new Date(ms).toISOString()} title={`${LAGOS.format(ms)} WAT`} className="tabular">
      {relativeLabel(ms, now)}
    </time>
  );
}

/** 15: money set properly (Naira fallback, muted decimals, tabular). */
export function Money({ amount, currency = "NGN" }: { amount: number; currency?: string }) {
  const parts = new Intl.NumberFormat("en-NG", { style: "currency", currency, minimumFractionDigits: 2 }).formatToParts(
    amount,
  );
  return (
    <span className="money">
      {parts.map((p, i) =>
        p.type === "fraction" || (p.type === "decimal" && parts[i + 1]?.type === "fraction") ? (
          <span key={i} className="money-dec">
            {p.value}
          </span>
        ) : (
          <React.Fragment key={i}>{p.value}</React.Fragment>
        ),
      )}
    </span>
  );
}

/** 84: go-to pairs. G then H Home, B Bridge, R code runner, A approvals, S settings, C connect. */
const GOTO: Record<string, string> = {
  h: "/",
  a: "/approvals",
  b: "/bridge",
  s: "/settings",
  c: "/connect",
};
export function goToKeysFor(href: string | null): string | null {
  if (!href) return null;
  const k = Object.keys(GOTO).find((key) => GOTO[key] === href);
  return k ? `G ${k.toUpperCase()}` : null;
}

function labelGoToLinks() {
  for (const k of Object.keys(GOTO)) {
    document.querySelectorAll<HTMLElement>(`a[href="${GOTO[k]}"]:not([data-shortcut])`).forEach((a) => a.setAttribute("data-shortcut", `G ${k.toUpperCase()}`));
  }
}

const COACH_KEY = "ingenium.shortcutCoach";
/** 83: counts clicks per shortcut; on the third, shows "Tip: press …" once ever. Returns true when it showed. */
export function coachShortcut(keys: string, notify: (msg: string) => void = (m) => toast(m)): boolean {
  try {
    const st = JSON.parse(localStorage.getItem(COACH_KEY) ?? "{}") as Record<string, number>;
    if (st[keys] === -1) return false;
    st[keys] = (st[keys] ?? 0) + 1;
    const show = st[keys] >= 3;
    if (show) st[keys] = -1;
    localStorage.setItem(COACH_KEY, JSON.stringify(st));
    if (show) notify(`Tip: press ${keys.replace(/^G /, "G then ")}`);
    return show;
  } catch {
    return false;
  }
}

export function GoToKeys() {
  const router = useRouter();
  React.useEffect(() => {
    let armed = 0;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (e.metaKey || e.ctrlKey || e.altKey || t?.closest("input,textarea,select,[contenteditable='true']")) return;
      const k = e.key.toLowerCase();
      const root = document.documentElement;
      if ((e.metaKey || e.ctrlKey) && k === ".") return;
      if (e.shiftKey && k === "b") {
        root.toggleAttribute("data-blueprint"); // 147
        return;
      }
      if (armed && Date.now() - armed < 1200 && GOTO[k]) {
        armed = 0;
        e.preventDefault();
        router.push(GOTO[k]);
        return;
      }
      if (e.key === "?") {
        e.preventDefault();
        window.dispatchEvent(new Event("ingenium:shortcuts")); // 89
        return;
      }
      // 86: J/K or arrows move through any [data-list-nav] list; X selects; Enter opens
      const list = (t?.closest("[data-list-nav]") ?? document.querySelector("[data-list-nav]")) as HTMLElement | null;
      if (list && ["j", "k", "x", "enter"].includes(k)) {
        const rows = Array.from(list.querySelectorAll<HTMLElement>("[data-list-row]"));
        if (rows.length) {
          const i = rows.findIndex((r) => r.hasAttribute("data-list-focus"));
          if (k === "j" || k === "k") {
            const n = Math.max(0, Math.min(rows.length - 1, i + (k === "j" ? 1 : -1)));
            rows.forEach((r) => r.removeAttribute("data-list-focus"));
            rows[n].setAttribute("data-list-focus", "");
            rows[n].scrollIntoView({ block: "nearest" });
            e.preventDefault();
            return;
          }
          if (i >= 0 && k === "x") rows[i].querySelector<HTMLInputElement>("input[type=checkbox]")?.click();
          if (i >= 0 && k === "enter") rows[i].querySelector<HTMLElement>("a,button")?.click();
        }
      }
      armed = k === "g" ? Date.now() : 0;
    };
    // 82: hold Cmd/Ctrl for half a second to show keycap hints on [data-shortcut] elements
    let hintTimer: number | undefined;
    const onDown = (e: KeyboardEvent) => {
      if ((e.key === "Meta" || e.key === "Control") && !hintTimer)
        hintTimer = window.setTimeout(() => {
          labelGoToLinks();
          document.documentElement.setAttribute("data-key-hints", "");
        }, 500);
      else if (hintTimer && e.key !== "Meta" && e.key !== "Control") clearHints();
    };
    const clearHints = () => {
      window.clearTimeout(hintTimer);
      hintTimer = undefined;
      document.documentElement.removeAttribute("data-key-hints");
    };
    const onMod = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === ".") {
        e.preventDefault();
        document.documentElement.toggleAttribute("data-focus-mode"); // 123
      } else if (e.key === "Escape" && document.documentElement.hasAttribute("data-focus-mode")) {
        document.documentElement.removeAttribute("data-focus-mode");
      }
    };
    if (localStorage.getItem("ingenium.readingComfort") === "on") document.documentElement.setAttribute("data-reading-comfort", "");
    if (localStorage.getItem("ingenium.odooDim") === "on") document.documentElement.setAttribute("data-odoo-dim", "");
    const d = localStorage.getItem("ingenium.density"); // 121
    if (d && d !== "comfortable") document.documentElement.setAttribute("data-density", d);
    // 83: after a third click on something with a shortcut, one quiet tip, once.
    const onClick = (e: MouseEvent) => {
      const el = (e.target as HTMLElement | null)?.closest<HTMLElement>("[data-shortcut],a[href]");
      if (!el || e.detail === 0) return; // keyboard activation needs no coaching
      const keys = el.getAttribute("data-shortcut") ?? goToKeysFor(el.getAttribute("href"));
      if (keys) coachShortcut(keys);
    };
    window.addEventListener("click", onClick, true);
    // 141: prefetch on intent. When the pointer rests on an in-app link for 80 ms, start loading it.
    const fetched = new Set<string>();
    let intent: number | undefined;
    const onOver = (e: PointerEvent) => {
      const a = (e.target as HTMLElement | null)?.closest<HTMLAnchorElement>("a[href^='/']");
      window.clearTimeout(intent);
      const href = a?.getAttribute("href");
      if (!href || href.startsWith("/api/") || fetched.has(href) || a?.target === "_blank") return;
      intent = window.setTimeout(() => {
        fetched.add(href);
        router.prefetch(href);
      }, 80);
    };
    window.addEventListener("pointerover", onOver, { passive: true });
    window.addEventListener("keydown", onKey);
    window.addEventListener("keydown", onMod);
    window.addEventListener("keydown", onDown);
    window.addEventListener("keyup", clearHints);
    window.addEventListener("blur", clearHints);
    return () => {
      window.removeEventListener("click", onClick, true);
      window.removeEventListener("pointerover", onOver);
      window.clearTimeout(intent);
      window.removeEventListener("keydown", onDown);
      window.removeEventListener("keyup", clearHints);
      window.removeEventListener("blur", clearHints);
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("keydown", onMod);
    };
  }, [router]);
  return null;
}

/** 34: hold to confirm (~1.2 s); letting go cancels. Keyboard: hold Enter/Space. */
export function HoldButton({
  onConfirm,
  children,
  className = "",
}: {
  onConfirm: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  const [holding, setHolding] = React.useState(false);
  const timer = React.useRef<number | undefined>(undefined);
  const start = () => {
    setHolding(true);
    timer.current = window.setTimeout(() => {
      setHolding(false);
      onConfirm();
    }, 1200);
  };
  const stop = () => {
    setHolding(false);
    window.clearTimeout(timer.current);
  };
  return (
    <button
      type="button"
      className={`hold-btn ${className}`}
      data-holding={holding ? "true" : "false"}
      onPointerDown={start}
      onPointerUp={stop}
      onPointerLeave={stop}
      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && !e.repeat && start()}
      onKeyUp={stop}
      aria-description="Press and hold to confirm"
    >
      {children}
    </button>
  );
}

/** 10: empty-state arch missing its keystone; the action sits in the gap. */
export function EmptyArch({ title, body, action }: { title: string; body?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center">
      <svg width="88" height="56" viewBox="0 0 88 56" fill="none" aria-hidden="true" className="text-muted">
        <path d="M8 54V32a36 32 0 0 1 72 0v22M20 54V32a24 22 0 0 1 48 0v22" stroke="currentColor" strokeWidth="1.5" />
      </svg>
      <p className="font-medium text-ink">{title}</p>
      {body ? <p className="max-w-sm text-sm text-muted">{body}</p> : null}
      {action}
    </div>
  );
}

/** 5: fill order from both legs toward the top; the keystone (top) is last. */
export function voussoirOrder(n: number): number[] {
  const out: number[] = [];
  for (let l = 0, r = n - 1; l <= r; l++, r--) {
    out.push(l);
    if (r !== l) out.push(r);
  }
  return out;
}

/** 6: one stone per health area; a weak area is a missing stone, named on hover. */
export function HealthArch({ score, parts, label = "Health" }: { score: number; parts: Array<{ key: string; label: string; score: number }>; label?: string }) {
  const n = Math.max(1, parts.length);
  const pt = (a: number, r: number) => `${50 + r * Math.cos(a)},${52 - r * Math.sin(a)}`;
  const weak = parts.filter((p) => p.score < 60).map((p) => p.label);
  return (
    <figure className="inline-flex flex-col items-center" aria-label={`${label}: ${Math.round(score)} of 100${weak.length ? `. Weak: ${weak.join(", ")}` : ""}`} data-testid="health-arch">
      <svg viewBox="0 0 100 54" width="120" height="65" aria-hidden="true">
        {parts.map((p, i) => {
          const a0 = Math.PI - (i / n) * Math.PI + 0.03;
          const a1 = Math.PI - ((i + 1) / n) * Math.PI - 0.03;
          const ok = p.score >= 60;
          return (
            <polygon key={p.key} points={`${pt(a0, 46)} ${pt(a1, 46)} ${pt(a1, 32)} ${pt(a0, 32)}`} fill={ok ? "var(--accent7)" : "none"} fillOpacity={ok ? 0.45 + (p.score / 100) * 0.55 : 1} stroke={ok ? "none" : "var(--border-strong, currentColor)"} strokeDasharray={ok ? undefined : "2 2"}>
              <title>{`${p.label}: ${p.score}`}</title>
            </polygon>
          );
        })}
      </svg>
      <span key={Math.round(score)} className="blur-bridge dot-numerals text-2xl text-ink">{Math.round(score)}</span>
    </figure>
  );
}

/** 5: voussoir progress: steps as arch stones; the keystone is the last. */
export function VoussoirProgress({ done, total, label }: { done: number; total: number; label?: string }) {
  const n = Math.max(1, total);
  return (
    <div role="progressbar" aria-valuemin={0} aria-valuemax={n} aria-valuenow={done} aria-label={label ?? "Progress"}>
      <svg viewBox="0 0 100 54" width="100" height="54" aria-hidden="true">
        {Array.from({ length: n }, (_, i) => {
          const a0 = Math.PI - (i / n) * Math.PI + 0.03;
          const a1 = Math.PI - ((i + 1) / n) * Math.PI - 0.03;
          const pt = (a: number, r: number) => `${50 + r * Math.cos(a)},${52 - r * Math.sin(a)}`;
          const rank = voussoirOrder(n).indexOf(i);
          const key = rank === n - 1;
          const fill = rank < done ? (key ? "var(--brand-cinnabar)" : "var(--accent7)") : "var(--surface-muted)";
          return <polygon key={i} points={`${pt(a0, 46)} ${pt(a1, 46)} ${pt(a1, 32)} ${pt(a0, 32)}`} fill={fill} />;
        })}
      </svg>
    </div>
  );
}

/** 6: arch health gauge (0-100); missing stones show what is unhealthy. */
export function ArchGauge({ score, label }: { score: number; label: string }) {
  const stones = 9;
  return (
    <div className="inline-flex flex-col items-center" aria-label={`${label}: ${Math.round(score)} of 100`}>
      <VoussoirProgress done={Math.round((score / 100) * stones)} total={stones} label={label} />
      <span key={Math.round(score)} className="blur-bridge tabular text-sm text-ink">{Math.round(score)}</span>
    </div>
  );
}

/** 107: honest three-bar confidence with the reason on hover. */
export function ConfidenceMark({ level, reason }: { level: 1 | 2 | 3; reason: string }) {
  const word = ["", "Low", "Medium", "High"][level];
  return (
    <span className="inline-flex items-end gap-[2px]" title={reason} aria-label={`${word} confidence: ${reason}`}>
      {[1, 2, 3].map((b) => (
        <span
          key={b}
          className="w-[3px] rounded-sm"
          style={{ height: 4 + b * 3, background: b <= level ? "var(--accent7)" : "var(--surface-muted)" }}
        />
      ))}
    </span>
  );
}

/** 109: provenance chip on AI-made items until a person edits them. */
export function ProvenanceChip({ by = "Expert" }: { by?: string }) {
  return (
    <span className="inline-flex items-center rounded-full border border-border-subtle px-2 py-[1px] text-xs text-muted">
      Drafted by {by}, checked by code
    </span>
  );
}

/** 29: a colour for each database (stable from its id). */
const DB_COLOURS = ["#0f766e", "#b45309", "#7c3aed", "#be185d", "#1d4ed8", "#4d7c0f", "#c2410c", "#0e7490"];
export function dbColour(id: string): string {
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return DB_COLOURS[h % DB_COLOURS.length];
}

/** 28: test copies feel different from live. */
/** Test copy or Live. The saved flag wins; older connections fall back to a name guess (certain: false). */
export function testCopyStatus(c: { db_name?: string; name?: string; write_mode?: string; is_test_copy?: boolean | null }): { test: boolean; certain: boolean } {
  if (typeof c.is_test_copy === "boolean") return { test: c.is_test_copy, certain: true };
  return { test: guessTestCopy(c), certain: false };
}

export function isTestCopy(c: { db_name?: string; name?: string; write_mode?: string; is_test_copy?: boolean | null }): boolean {
  return testCopyStatus(c).test;
}

function guessTestCopy(c: { db_name?: string; name?: string; write_mode?: string }): boolean {
  if (c.write_mode === "production") return false;
  return /(^|[_\-. ])(test|staging|stage|demo|sandbox|dev|uat)([_\-. ]|$)/i.test(`${c.db_name ?? ""} ${c.name ?? ""}`);
}

/** Touch 69: calm offline band with the count of waiting changes. */
export function OfflineBand({ waiting = 0 }: { waiting?: number }) {
  const [offline, setOffline] = React.useState(false);
  React.useEffect(() => {
    const sync = () => setOffline(!navigator.onLine);
    sync();
    window.addEventListener("online", sync);
    window.addEventListener("offline", sync);
    return () => {
      window.removeEventListener("online", sync);
      window.removeEventListener("offline", sync);
    };
  }, []);
  if (!offline) return null;
  return (
    <div className="offline-band" role="status" data-testid="offline-band">
      Offline. Your changes are saved here and will send when you&apos;re back
      {waiting > 0 ? ` (${waiting}\u00a0waiting)` : ""}.
    </div>
  );
}

/** Touch 66: loading that tells the truth over time. */
export function SlowHint({ onCancel, base = "Reading your database" }: { onCancel?: () => void; base?: string }) {
  const [stage, setStage] = React.useState(0);
  React.useEffect(() => {
    const ts = [2000, 6000, 15000].map((ms, i) => window.setTimeout(() => setStage(i + 1), ms));
    return () => ts.forEach((t) => window.clearTimeout(t));
  }, []);
  if (stage === 0) return null;
  return (
    <p className="text-sm text-muted" role="status" data-testid="slow-hint">
      {stage === 1 ? `${base}…` : "Odoo is answering slowly today."}
      {stage >= 3 && onCancel ? (
        <button type="button" className="ml-2 underline" onClick={onCancel} data-testid="slow-hint-cancel">
          Cancel
        </button>
      ) : null}
    </p>
  );
}

/** 150: on 1 October and 12 June (Lagos dates) the inbox-zero drawing gains a quiet green-white-green ground line. */
export function seasonalArch(now: Date = new Date()): "independence" | "democracy" | null {
  const lagos = new Date(now.getTime() + 60 * 60_000);
  const md = `${lagos.getUTCMonth() + 1}-${lagos.getUTCDate()}`;
  return md === "10-1" ? "independence" : md === "6-12" ? "democracy" : null;
}

/** Touch 72: composed "all clear" instead of blank space. */
export function AllClear({ title, checkedAt }: { title: string; checkedAt?: string | Date }) {
  return (
    <div className="flex flex-col items-center gap-2 py-10 text-center" data-testid="all-clear">
      <svg width="64" height="40" viewBox="0 0 88 56" fill="none" aria-hidden="true" className="text-muted">
        <path d="M8 54V32a36 32 0 0 1 72 0v22M20 54V32a24 22 0 0 1 48 0v22" stroke="currentColor" strokeWidth="1.5" />
        <path d="M39 1h10l-1.5 11h-7z" fill="var(--brand-cinnabar)" />
        {seasonalArch() ? (
          <g aria-hidden="true" data-testid="seasonal-arch">
            <path d="M2 55h28" stroke="#008751" strokeWidth="1.5" />
            <path d="M30 55h28" stroke="currentColor" strokeOpacity="0.25" strokeWidth="1.5" />
            <path d="M58 55h28" stroke="#008751" strokeWidth="1.5" />
          </g>
        ) : null}
      </svg>
      <p className="text-sm font-semibold text-ink">{title}</p>
      {checkedAt ? (
        <p className="text-xs text-muted">
          Checked <RelativeTime value={checkedAt} />
        </p>
      ) : null}
    </div>
  );
}

/** Touch 11: living favicon — badge count of waiting approvals; dims while a long run is busy. */
export function useLivingFavicon(count: number, busy = false) {
  React.useEffect(() => {
    if (typeof document === "undefined") return;
    const link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (!link) return;
    const original = link.href;
    if (count <= 0 && !busy) return;
    const img = new Image();
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = c.height = 32;
      const g = c.getContext("2d");
      if (!g) return;
      g.globalAlpha = busy ? 0.5 : 1;
      g.drawImage(img, 0, 0, 32, 32);
      g.globalAlpha = 1;
      if (count > 0) {
        g.fillStyle = "#0f766e"; // teal: waiting is not committed (touch 3)
        g.beginPath();
        g.arc(23, 9, 9, 0, Math.PI * 2);
        g.fill();
        g.fillStyle = "#fff";
        g.font = "bold 12px sans-serif";
        g.textAlign = "center";
        g.textBaseline = "middle";
        g.fillText(count > 9 ? "9+" : String(count), 23, 10);
      }
      link.href = c.toDataURL("image/png");
    };
    img.src = original;
    return () => {
      link.href = original;
    };
  }, [count, busy]);
}

/** Pages announce waiting approvals / long runs; the shell updates the favicon (touch 11). */
export function announceFavicon(detail: { count?: number; busy?: boolean }) {
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("ingenium:favicon", { detail }));
}

/** Dims the tab icon while `active` (a long run) is true. */
export function useTabBusy(active: boolean) {
  React.useEffect(() => {
    if (!active) return;
    announceFavicon({ busy: true });
    return () => announceFavicon({ busy: false });
  }, [active]);
}

export function FaviconBridge() {
  const [s, setS] = React.useState({ count: 0, busy: false });
  React.useEffect(() => {
    const on = (e: Event) => setS((p) => ({ ...p, ...(e as CustomEvent).detail }));
    window.addEventListener("ingenium:favicon", on);
    // Poll the waiting-approvals count so the badge works from any page or tab.
    let alive = true;
    const poll = async () => {
      try {
        const b = await request<{ count?: unknown }>("/api/command/tiles/pending-approvals");
        if (alive && typeof b.count === "number") setS((p) => ({ ...p, count: b.count as number }));
      } catch {
        /* the plain icon is the honest fallback */
      }
    };
    void poll();
    const t = window.setInterval(poll, 60_000);
    return () => {
      alive = false;
      window.clearInterval(t);
      window.removeEventListener("ingenium:favicon", on);
    };
  }, []);
  useLivingFavicon(s.count, s.busy);
  return null;
}

const SHORTCUTS: Array<[string, string]> = [
  ["Mod+K", "Find anything"],
  ["G H", "Go home"],
  ["G B", "Go to Bridge"],
  ["G R", "Go to the code runner"],
  ["G A", "Go to approvals"],
  ["G C", "Go to Connect"],
  ["J K", "Move through a list"],
  ["X", "Select the row"],
  ["Enter", "Open the row"],
  ["Mod+.", "Focus mode"],
  ["Shift+B", "Blueprint view on a canvas"],
  ["Mod+Enter", "Confirm the main action in a dialog"],
  ["Esc", "Step back one level"],
  ["?", "This sheet"],
];

/** Touch 89: "?" opens a printable shortcut sheet laid out like a manual page. */
export function ShortcutSheet() {
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    const on = () => setOpen((o) => !o);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("ingenium:shortcuts", on);
    window.addEventListener("keydown", esc);
    return () => {
      window.removeEventListener("ingenium:shortcuts", on);
      window.removeEventListener("keydown", esc);
    };
  }, []);
  if (!open) return null;
  return (
    <div className="shortcut-sheet overlay-dim" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts" data-testid="shortcut-sheet" onClick={() => setOpen(false)}>
      <section className="shortcut-card hairline" onClick={(e) => e.stopPropagation()}>
        <header className="flex items-baseline justify-between">
          <h2 className="text-base font-semibold text-ink">Keyboard shortcuts</h2>
          <button type="button" className="text-sm underline" onClick={() => window.print()}>
            Print
          </button>
        </header>
        <dl className="shortcut-grid">
          {SHORTCUTS.map(([keys, what]) => (
            <React.Fragment key={keys}>
              <dt>
                {keys.split(" ").map((kk) => (
                  <Keycap key={kk} keys={kk} />
                ))}
              </dt>
              <dd>{what}</dd>
            </React.Fragment>
          ))}
        </dl>
        <p className="text-xs text-muted">Hold Cmd or Ctrl for half a second to see shortcuts on the page.</p>
      </section>
    </div>
  );
}

/** Touch 146: background work pill — pages call announceJob; the top bar shows running jobs. */
export type BgJob = { id: string; label: string; done?: number; total?: number };
export function announceJob(job: BgJob | { id: string; finished: true }) {
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("ingenium:job", { detail: job }));
}
export function BackgroundWorkPill() {
  const [jobs, setJobs] = React.useState<Record<string, BgJob>>({});
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    const on = (e: Event) => {
      const j = (e as CustomEvent).detail as BgJob & { finished?: boolean };
      setJobs((m) => {
        const n = { ...m };
        if (j.finished) delete n[j.id];
        else n[j.id] = j;
        return n;
      });
    };
    window.addEventListener("ingenium:job", on);
    return () => window.removeEventListener("ingenium:job", on);
  }, []);
  const list = Object.values(jobs);
  announceFaviconBusy(list.length > 0);
  if (!list.length) return null;
  return (
    <div className="relative" data-testid="bg-work-pill">
      <button type="button" className="bg-pill" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {list.length === 1 ? list[0].label : `${list.length}\u00a0jobs running`}
      </button>
      {open ? (
        <ul className="bg-pill-menu hairline">
          {list.map((j) => (
            <li key={j.id}>
              {j.label}
              {j.total ? ` — ${j.done ?? 0} of ${j.total}` : ""}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
let lastBusy = false;
function announceFaviconBusy(busy: boolean) {
  if (busy === lastBusy) return;
  lastBusy = busy;
  queueMicrotask(() => announceFavicon({ busy }));
}

/** Touch 16: rolling digits. Only the digits that changed roll in; text content stays the plain number. */
export function RollingNumber({ value, format = (n: number) => n.toLocaleString("en-NG") }: { value: number; format?: (n: number) => string }) {
  const text = format(value);
  const chars = text.split("");
  return (
    <span className="rolling-num tabular" aria-live="polite">
      {chars.map((ch, i) => (
        <span key={`${chars.length - i}-${ch}`} className={/\d/.test(ch) ? "rolling-digit" : undefined}>{ch}</span>
      ))}
    </span>
  );
}

/** Touch 55: sparkline in ink; accent only on the latest point. */
export function Sparkline({ values, width = 64, height = 16, label, ghost }: { values: number[]; width?: number; height?: number; label: string; ghost?: string }) {
  if (values.length < 2 || (ghost && values.every((v) => v === 0))) {
    if (!ghost) return null;
    // 62: ghost chart. A faint outline that says when it fills in.
    const d = Array.from({ length: 9 }, (_, i) => `${(i / 8) * (width - 2) + 1},${height / 2 + Math.sin(i * 1.1) * (height / 4)}`).join(" ");
    return (
      <svg className="sparkline sparkline-ghost" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label}: ${ghost}`}>
        <title>{ghost}</title>
        <polyline points={d} fill="none" stroke="currentColor" strokeWidth="1" strokeDasharray="2 2" />
      </svg>
    );
  }
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  const pts = values.map((v, i) => [(i / (values.length - 1)) * (width - 2) + 1, height - 1 - ((v - min) / span) * (height - 2)] as const);
  const last = pts[pts.length - 1];
  return (
    <svg className="sparkline" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${label}: latest ${values[values.length - 1]}`}>
      <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke="currentColor" strokeWidth="1" />
      <circle cx={last[0]} cy={last[1]} r="1.75" className="sparkline-last" />
    </svg>
  );
}

/** 63: every chart has a table. A small switch swaps the chart for its numbers. */
export function WithTable({ label, rows, children }: { label: string; rows: Array<[string, string | number]>; children: React.ReactNode }) {
  const [table, setTable] = React.useState(false);
  return (
    <span className="with-table">
      {table ? (
        <table className="chart-table" aria-label={label}>
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k}><th scope="row">{k}</th><td className="tabular">{v}</td></tr>
            ))}
          </tbody>
        </table>
      ) : children}
      <button type="button" className="chart-table-toggle" aria-pressed={table} onClick={() => setTable((t) => !t)} data-testid="chart-table-toggle">
        {table ? "Chart" : "Table"}
      </button>
    </span>
  );
}

/** Touch 56: tiny fill-rate bar. How full a field is in real data. Hidden when unknown. */
export function FillBar({ ratio, label }: { ratio: number | null | undefined; label: string }) {
  if (ratio == null) return null;
  const pct = Math.round(ratio * 100);
  return (
    <span className="fill-bar" role="img" aria-label={`${label}: filled on ${pct}% of records`} title={`Filled on ${pct}% of records`} data-low={pct < 20 ? "" : undefined}>
      <span style={{ inlineSize: `${Math.max(pct, 2)}%` }} />
    </span>
  );
}

/** Touch 79: count next to the pointer while selecting several items ("6 fields"). */
export function SelectionCount({ count, noun = "items" }: { count: number; noun?: string }) {
  const pos = React.useRef({ x: 0, y: 0 });
  const [show, setShow] = React.useState<{ x: number; y: number } | null>(null);
  React.useEffect(() => {
    const on = (e: PointerEvent) => { pos.current = { x: e.clientX, y: e.clientY }; };
    window.addEventListener("pointerdown", on, true);
    window.addEventListener("pointermove", on, { passive: true });
    return () => {
      window.removeEventListener("pointerdown", on, true);
      window.removeEventListener("pointermove", on);
    };
  }, []);
  React.useEffect(() => {
    if (count < 2) return setShow(null);
    setShow({ ...pos.current });
    const t = window.setTimeout(() => setShow(null), 1200);
    return () => window.clearTimeout(t);
  }, [count]);
  return (
    <>
      <span className="sr-only" aria-live="polite">{count > 1 ? `${count} ${noun} selected` : ""}</span>
      {show ? <span className="selection-count tabular" style={{ left: show.x + 14, top: show.y + 14 }} aria-hidden="true">{count} {noun}</span> : null}
    </>
  );
}

/** Touch 57: before/after dumbbell for a count a plan changes. */
export function Dumbbell({ before, after, max, label }: { before: number; after: number; max: number; label: string }) {
  const pct = (n: number) => `${Math.max(0, Math.min(100, (n / (max || 1)) * 100))}%`;
  const lo = Math.min(before, after);
  const hi = Math.max(before, after);
  return (
    <span className="dumbbell" role="img" aria-label={`${label}: ${before} to ${after}`} data-dir={after >= before ? "up" : "down"}>
      <span className="dumbbell-bar" style={{ left: pct(lo), width: `calc(${pct(hi)} - ${pct(lo)})` }} />
      <span className="dumbbell-dot dumbbell-before" style={{ left: pct(before) }} />
      <span className="dumbbell-dot dumbbell-after" style={{ left: pct(after) }} />
    </span>
  );
}

/** Touch 47: edit in place. Click to edit, Enter saves, Esc reverts. */
export function EditInPlace({ value, onSave, label }: { value: string; onSave: (next: string) => void; label: string }) {
  const [editing, setEditing] = React.useState(false);
  const [draft, setDraft] = React.useState(value);
  if (!editing) {
    return (
      <button type="button" className="edit-in-place" aria-label={`${label}: ${value}. Click to edit`} onClick={() => { setDraft(value); setEditing(true); }}>
        {value}
      </button>
    );
  }
  return (
    <input
      className="edit-in-place-input"
      aria-label={label}
      autoFocus
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={() => setEditing(false)}
      onKeyDown={(e) => {
        if (e.key === "Enter") { const t = draft.trim(); if (t && t !== value) onSave(t); setEditing(false); }
        if (e.key === "Escape") { setDraft(value); setEditing(false); }
      }}
    />
  );
}

/** Touch 44: scrub a number label left/right; Shift = 10x steps. Arrow keys work too. */
export function ScrubNumber({ value, onChange, step = 1, min = -Infinity, max = Infinity, label, children }: { value: number; onChange: (n: number) => void; step?: number; min?: number; max?: number; label: string; children?: React.ReactNode }) {
  const clamp = (n: number) => Math.min(max, Math.max(min, n));
  return (
    <span
      className="scrub-number tabular"
      role="spinbutton"
      tabIndex={0}
      aria-label={label}
      aria-valuenow={value}
      onKeyDown={(e) => {
        const k = e.shiftKey ? 10 : 1;
        if (e.key === "ArrowUp" || e.key === "ArrowRight") { e.preventDefault(); onChange(clamp(value + step * k)); }
        if (e.key === "ArrowDown" || e.key === "ArrowLeft") { e.preventDefault(); onChange(clamp(value - step * k)); }
      }}
      onPointerDown={(e) => {
        const start = e.clientX;
        const base = value;
        const el = e.currentTarget;
        el.setPointerCapture?.(e.pointerId);
        const move = (ev: PointerEvent) => onChange(clamp(base + Math.round((ev.clientX - start) / 4) * step * (ev.shiftKey ? 10 : 1)));
        const up = () => { el.removeEventListener("pointermove", move); el.removeEventListener("pointerup", up); };
        el.addEventListener("pointermove", move);
        el.addEventListener("pointerup", up);
      }}
    >
      {children ?? value}
    </span>
  );
}
