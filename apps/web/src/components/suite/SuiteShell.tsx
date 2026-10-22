"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { IconAccess as Shield, IconAutomations as Zap, IconCron as Clock, IconDraftStudio as FilePen, IconOdooExpert as Bot, IconSnapshots as History, IconViews as LayoutPanelTop, Lock, Package, Search } from "@/components/ui/icons";
import { authApi } from "@/lib/api/auth";
import { changeApi, suiteApi } from "@/lib/api/suite";
import { SuiteProvider, useSuite } from "./SuiteContext";
import { BotAvatar, type BotState } from "./BotAvatar";
import { PassportCard, fmtWhen } from "./parts";
import styles from "./Suite.module.css";

type RailItem = { href: string; label: string; icon?: typeof Bot; sub?: boolean; match?: string };

function rail(id: string): RailItem[] {
  const s = `/connections/${id}/suite`;
  return [
    { href: s, label: "Home", icon: LayoutPanelTop },
    { href: `${s}/ask`, label: "Ask", icon: Bot },
    { href: `${s}/explore/capabilities`, label: "Explore", icon: Search, match: `${s}/explore` },
    { href: `${s}/explore/insights`, label: "Look closer", sub: true },
    { href: `${s}/change/edit`, label: "Change records", icon: FilePen, match: `${s}/change` },
    { href: `${s}/change/transitions`, label: "Move forward", sub: true },
    { href: `${s}/change/edit`, label: "Edit a field", sub: true },
    { href: `${s}/change/duplicates`, label: "Merge duplicates", sub: true },
    { href: `${s}/change/activities`, label: "Activities", sub: true },
    { href: `${s}/change/portal`, label: "Portal access", sub: true },
    { href: `${s}/change/records`, label: "Record editor", sub: true },
    { href: `${s}/upkeep/schedules`, label: "Upkeep", icon: Clock, match: `${s}/upkeep` },
    { href: `${s}/safety/check`, label: "Safety", icon: Shield, match: `${s}/safety` },
    { href: `${s}/setup`, label: "Set up", icon: Package },
  ];
}

function TopBar() {
  const { home, error, readAt } = useSuite();
  const [open, setOpen] = useState(false);
  const p = home?.passport;
  return (
    <header className={styles.top}>
      <button type="button" className={styles.passport} aria-expanded={open} aria-controls="suite-passport" onClick={() => setOpen((v) => !v)} data-testid="suite-passport-chip">
        {p ? (
          <>
            <strong>{p.database}</strong>
            <span className={styles.muted}>Odoo {p.version} {p.edition === "enterprise" ? "Enterprise" : p.edition === "community" ? "Community" : ""} · {p.apps.length} apps{readAt ? ` · read ${readAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : ""}</span>
          </>
        ) : (
          <span className={styles.muted}>{error ? "Can't read this database" : "Reading the database…"}</span>
        )}
      </button>
      <span className={styles.spacer} />
      {home ? (
        <span className={styles.writes} data-on={home.writes.on} data-testid="suite-writes">
          {home.writes.on ? <Zap aria-hidden /> : <Lock aria-hidden />}
          Writes: {home.writes.on ? "On" : "Off"}
        </span>
      ) : null}
      {open && p ? <div id="suite-passport" className={styles.popover}><PassportCard /></div> : null}
    </header>
  );
}

function RunsTray({ connectionId }: { connectionId: string }) {
  const [runs, setRuns] = useState<{ id: string; name: string; state: string; href: string; fire_at?: string | null; change?: boolean; repeat?: { every: string } | null }[]>([]);
  const [nonce, setNonce] = useState(0);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const tick = () => {
      Promise.all([suiteApi.runs(connectionId), changeApi.runs(connectionId).catch(() => ({ runs: [] }))]).then(([s, c]) => {
        if (!live) return;
        const setup = s.runs.map((x) => ({ ...x, href: `/connections/${connectionId}/suite/setup?run=${x.id}&view=run` }));
        const change = c.runs.map((x) => ({ ...x, change: true, href: `/connections/${connectionId}/suite/change/${x.tool}?batch=${x.batch_id}` }));
        const all = [...setup, ...change].sort((a, b) => String(b.started_at).localeCompare(String(a.started_at)));
        const scheduled = all.filter((x) => x.state === "scheduled");
        setRuns([...scheduled, ...all.filter((x) => x.state !== "scheduled")].slice(0, Math.max(5, scheduled.length)));
        const busy = all.some((x) => x.state === "running" || x.state === "queued");
        timer = setTimeout(tick, busy ? 3000 : 20000);
      }, () => { if (live) timer = setTimeout(tick, 30000); });
    };
    tick();
    return () => { live = false; if (timer) clearTimeout(timer); };
  }, [connectionId, nonce]);
  const running = runs.filter((r) => r.state === "running" || r.state === "queued").length;
  return (
    <section className={styles.tray} aria-label="Runs" data-testid="suite-runs-tray">
      <div className={styles.row}><History aria-hidden width={14} height={14} /> <strong>Runs</strong>{running ? <span>({running} running)</span> : null}</div>
      {runs.length ? (
        <ul>
          {runs.map((r) => (
            <li key={r.id}>
              <BotAvatar bot={r.change ? "runner" : "builder"} size={20} state={runState(r.state)} />{" "}
              <Link href={r.href}>{r.name}</Link>{" "}
              {r.state === "scheduled" ? (
                <>
                  <span className={styles.muted}>sends {fmtWhen(r.fire_at)}{r.repeat ? `, repeats ${r.repeat.every}` : ""}</span>{" "}
                  <button type="button" className={styles.linkBtn} onClick={() => changeApi.cancel(connectionId, r.id).then(() => setNonce((n) => n + 1), () => setMsg("It already started, so it can't be cancelled."))} data-testid="tray-cancel">Cancel</button>
                </>
              ) : <span className={styles.muted}>{r.state}</span>}
            </li>
          ))}
        </ul>
      ) : <p className={styles.muted}>No runs yet.</p>}
      {msg ? <p role="status" className={styles.muted}>{msg}</p> : null}
    </section>
  );
}

function Rail({ connectionId }: { connectionId: string }) {
  const path = usePathname() ?? "";
  const admin = useSuiteAdmin();
  const items = admin ? [...rail(connectionId), { href: `/connections/${connectionId}/suite/states`, label: "States preview", sub: true }] : rail(connectionId);
  const root = `/connections/${connectionId}/suite`;
  return (
    <nav className={styles.rail} aria-label="Suite">
      {items.map((it) => {
        const active = it.sub ? path === it.href : it.href === root ? path === root : path.startsWith(it.match ?? it.href);
        const Icon = it.icon;
        return (
          <Link key={`${it.label}-${it.href}`} href={it.href} className={[styles.railLink, it.sub ? styles.railSub : ""].join(" ")} aria-current={active ? "page" : undefined}>
            {Icon ? <Icon aria-hidden /> : null}
            {it.label}
          </Link>
        );
      })}
      <RunsTray connectionId={connectionId} />
    </nav>
  );
}

/** Suite shell (spec 4.1): passport chip with no version switcher, Writes state, rail of workspaces, Runs tray. */
export function SuiteShell({ connectionId, children }: { connectionId: string; children: ReactNode }) {
  return (
    <SuiteProvider connectionId={connectionId}>
      <div className={styles.shell} data-testid="suite-shell">
        <TopBar />
        <div className={styles.body}>
          <Rail connectionId={connectionId} />
          <main className={styles.main} id="suite-main">{children}</main>
        </div>
      </div>
    </SuiteProvider>
  );
}

function runState(state: string): BotState {
  if (state === "queued") return "thinking";
  if (state === "running") return "working";
  if (state === "failed" || state === "paused" || state === "stopped") return "needs_you";
  return state === "done" ? "done" : "idle";
}

/** Workspace owners and admins (or a local install without accounts) see design tools such as the states preview. */
function useSuiteAdmin(): boolean {
  const [admin, setAdmin] = useState(false);
  useEffect(() => {
    let live = true;
    authApi.authStatus().then(async (st) => {
      if (!st.auth_enabled || st.auth_mode !== "accounts") { if (live) setAdmin(!st.auth_enabled); return; }
      const me = await authApi.accountMe();
      if (live) setAdmin(me.user.is_superadmin || ["owner", "admin"].includes(me.workspace.role));
    }).catch(() => { if (live) setAdmin(false); });
    return () => { live = false; };
  }, []);
  return admin;
}
