"use client";

import { readRecent } from "@/lib/recentRecords";
import { readShell, useHydrated, writeShell } from "@/lib/shellCache";
import { connectionTag } from "@/components/shell/ConnectionSwitcher";
import { takeIntro } from "@/lib/readiness";
import { toast } from "sonner";
import { PageMove } from "@/components/shell/PageMove";
import { FaviconBridge, OfflineBand, ShortcutSheet, isTestCopy } from "@/components/ui/craft";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/Button";
import { ExpertPanel } from "@/components/expert/ExpertPanel";
import { ExpertBubble } from "@/components/expert/ExpertBubble";
import { Callout } from "@/components/ui/Callout";
import { Skeleton } from "@/components/ui/layout-primitives";
import { CommandPalette, type CommandItem } from "@/components/ui/CommandPalette";
import { Sidebar } from "@/components/shell/Sidebar";
import { TopBar } from "@/components/shell/TopBar";
import { ExpertDiagnoseListener } from "@/lib/expert-diagnostics";
import { useShell } from "@/context/ShellContext";
import { api } from "@/lib/api";
import { changeApi, suiteApi } from "@/lib/api/suite";
import { NAV_ITEMS } from "@/lib/nav";

type Props = {
  connectionId: string;
  children: React.ReactNode;
};

export function AppShell({ connectionId, children }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const {
    commandOpen,
    setCommandOpen,
    setExpertOpen,
    openExpert,
    setUiContext,
    uiContext,
  } = useShell();

  const [commandSearch, setCommandSearch] = useState("");

  // 142: the device cache is read only after mount, so the first client render matches the server (no hydration mismatch).
  const hydrated = useHydrated();
  const connectionQuery = useQuery({
    queryKey: ["connection", connectionId],
    queryFn: async () => { const c = await api.getConnection(connectionId); writeShell(`connection:${connectionId}`, c); return c; },
    placeholderData: () => (hydrated ? readShell(`connection:${connectionId}`) : undefined),
    enabled: Boolean(connectionId),
    retry: false,
    refetchOnWindowFocus: false,
  });

  const connectionsQuery = useQuery({
    queryKey: ["connections"],
    queryFn: async () => { const l = await api.listConnections(); writeShell("connections", l); return l; },
    placeholderData: () => (hydrated ? readShell("connections") : undefined),
    retry: false,
    refetchOnWindowFocus: false,
  });

  // Touch 128: one quiet introduction per power feature, once the person is ready.
  useEffect(() => {
    const intro = takeIntro();
    if (!intro) return;
    const href = intro.href(connectionId ?? null);
    toast(intro.message, href ? { action: { label: "Show me", onClick: () => router.push(href) } } : undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const [slowLoad, setSlowLoad] = useState(false);
  useEffect(() => {
    if (!connectionQuery.isPending) {
      setSlowLoad(false);
      return;
    }
    const t = window.setTimeout(() => setSlowLoad(true), 3_000);
    return () => window.clearTimeout(t);
  }, [connectionQuery.isPending]);

  const modelsQuery = useQuery({
    queryKey: ["models", connectionId],
    // 143: the schema is kept on this device, so search over record types is instant and works offline.
    queryFn: async () => { const m = await api.listModels(connectionId, true); writeShell(`models:${connectionId}`, m); return m; },
    placeholderData: () => (hydrated ? readShell(`models:${connectionId}`) : undefined),
    staleTime: 10 * 60_000,
    enabled: commandOpen,
  });

  const suggestedPromptsQuery = useQuery({
    queryKey: ["expert-suggested-prompts", pathname, uiContext.model],
    queryFn: () =>
      api.expertSuggestedPrompts({
        route: pathname,
        model: uiContext.model,
        view_type: uiContext.viewType,
        draft_summary: uiContext.draftSummary,
      }),
    enabled: commandOpen,
    staleTime: 60_000,
  });

  const automationsQuery = useQuery({
    queryKey: ["cmdk-automations", connectionId],
    queryFn: () => api.listAutomations(connectionId),
    enabled: commandOpen,
    staleTime: 60_000,
  });
  const menusQuery = useQuery({
    queryKey: ["cmdk-menus", connectionId],
    queryFn: () => api.listMenus(connectionId),
    enabled: commandOpen,
    staleTime: 300_000,
  });
  // ⌘K batch plans: saved Bulk Setup plans and Change batches open straight from the palette.
  const suitePlansQuery = useQuery({
    queryKey: ["cmdk-suite-plans", connectionId],
    queryFn: async () => {
      const [p, b] = await Promise.allSettled([suiteApi.plans(connectionId), changeApi.batches(connectionId)]);
      return { plans: p.status === "fulfilled" ? p.value.plans : [], batches: b.status === "fulfilled" ? b.value.batches : [] };
    },
    enabled: commandOpen,
    staleTime: 30_000,
  });
  const runsQuery = useQuery({
    queryKey: ["cmdk-runs", connectionId],
    queryFn: () => api.listScriptRuns(connectionId),
    enabled: commandOpen,
    staleTime: 30_000,
  });
  const historyQuery = useQuery({
    queryKey: ["cmdk-history", connectionId],
    queryFn: () => api.listSnapshots(connectionId),
    enabled: commandOpen,
    staleTime: 30_000,
  });

  // A6: remember recent pages for "Recent" in Find anything.
  useEffect(() => {
    try {
      const key = `ingenium.recent.${connectionId}`;
      const prev: string[] = JSON.parse(localStorage.getItem(key) ?? "[]");
      localStorage.setItem(key, JSON.stringify([pathname, ...prev.filter((p) => p !== pathname)].slice(0, 6)));
    } catch {
      /* storage unavailable */
    }
  }, [connectionId, pathname]);

  const nlSearchQuery = useQuery({
    queryKey: ["expert-nl-search", connectionId, commandSearch],
    queryFn: () => api.expertNLSearch({ query: commandSearch, connection_id: connectionId }),
    enabled: commandOpen && commandSearch.trim().length >= 4,
  });

  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const update = () => setOffline(typeof navigator !== "undefined" && !navigator.onLine);
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);

  useEffect(() => {
    setUiContext({ route: pathname });
  }, [pathname, setUiContext]);

  useEffect(() => {
    if (searchParams.get("expert") === "1") {
      setExpertOpen(true);
    }
    const resIdRaw = searchParams.get("res_id");
    const model = searchParams.get("model");
    if (resIdRaw || model) {
      setUiContext({
        ...(model ? { model } : {}),
        ...(resIdRaw ? { resId: Number.parseInt(resIdRaw, 10) } : {}),
      });
    }
  }, [searchParams, setExpertOpen, setUiContext]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen(true);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [setCommandOpen]);

  const commandItems = useMemo(() => {
    const navs = NAV_ITEMS.filter((n) => n.shipped !== false);
    const items: CommandItem[] = [];
    let recent: string[] = [];
    try {
      recent = JSON.parse(localStorage.getItem(`ingenium.recent.${connectionId}`) ?? "[]");
    } catch {
      recent = [];
    }
    for (const path of recent.slice(1)) {
      const nav = navs.find((n) => n.href(connectionId) === path);
      if (nav) items.push({ id: `recent-${nav.id}`, label: nav.label, group: "Recent", keywords: ["recent"], onSelect: () => router.push(path) });
    }
    for (const n of navs) {
      items.push({
        id: n.id,
        label: n.label,
        group: "Pages",
        keywords: [n.group],
        detail: n.group,
        onSelect: () => router.push(n.href(connectionId)),
      });
    }
    const base = `/connections/${connectionId}`;
    // Connection switcher in Cmd-K: jump to any saved connection, see them all, or add one.
    for (const c of (connectionsQuery.data ?? []).filter((x) => x.id !== connectionId).slice(0, 50)) {
      items.push({ id: `switch-${c.id}`, label: `Switch to ${c.name}`, group: "Connections", keywords: ["switch", "connection", "database", c.db_name ?? ""], detail: connectionTag(c), onSelect: () => router.push(`/connections/${c.id}`) });
    }
    items.push({ id: "switch-all", label: "All connections", group: "Connections", keywords: ["switch", "connections", "connect"], onSelect: () => router.push("/connect") });
    items.push({ id: "switch-add", label: "Add connection", group: "Connections", keywords: ["new", "connect", "database", "add"], onSelect: () => router.push("/connect#new") });
    for (const rr of hydrated ? readRecent(connectionId) : []) {
      items.push({
        id: `recent-rec-${rr.model}-${rr.id}`,
        label: rr.name,
        group: "Recent records",
        keywords: [rr.model, String(rr.id)],
        detail: `${rr.model} #${rr.id}`,
        onSelect: () => router.push(`${base}/suite/change/records?model=${encodeURIComponent(rr.model)}&open=${rr.id}`),
      });
    }
    for (const model of modelsQuery.data ?? []) {
      const m = encodeURIComponent(model.model);
      items.push({
        id: `model-${model.model}`,
        label: model.name ? `${model.name}` : model.model,
        group: "Record types",
        keywords: [model.model],
        detail: model.model,
        onSelect: () => router.push(`${base}/builder?model=${m}`),
        actions: [
          { id: `fields-${m}`, label: "Add or edit fields", onSelect: () => router.push(`${base}/builder?model=${m}`) },
          { id: `layout-${m}`, label: "Change the form layout", onSelect: () => router.push(`${base}/view-designer?model=${m}`) },
          { id: `auto-${m}`, label: "See automations", onSelect: () => router.push(`${base}/automations?model=${m}`) },
          { id: `ask-${m}`, label: "Ask Expert about it", onSelect: () => openExpert({ question: `Explain ${model.model} in this database`, autoSubmit: true, freshThread: true }) },
        ],
      });
    }
    for (const menu of menusQuery.data ?? []) {
      items.push({
        id: `menu-${menu.id}`,
        label: menu.parent_name ? `${menu.parent_name} / ${menu.name}` : menu.name,
        group: "Menus",
        keywords: ["menu"],
        detail: menu.action ? `Opens ${menu.action}` : "Menu folder",
        onSelect: () => router.push(`${base}/menus?menu=${menu.id}`),
      });
    }
    for (const a of automationsQuery.data ?? []) {
      items.push({
        id: `automation-${a.id}`,
        label: a.name,
        group: "Automations",
        keywords: [a.model, "automation"],
        detail: `${a.active ? "On" : "Off"} · ${a.model} · ${a.trigger}`,
        onSelect: () => router.push(`${base}/automations?id=${a.id}`),
      });
    }
    for (const sp of (suitePlansQuery.data?.plans ?? []).slice(0, 15)) {
      items.push({
        id: `suite-plan-${sp.id}`,
        label: sp.name,
        group: "Batch plans",
        keywords: ["plan", "setup", "bulk", "batch"],
        detail: `Setup plan · ${sp.steps} step${sp.steps === 1 ? "" : "s"}`,
        onSelect: () => router.push(`${base}/suite/setup?plan=${sp.id}&view=board`),
        actions: [
          { id: `suite-plan-check-${sp.id}`, label: "Open and check it", onSelect: () => router.push(`${base}/suite/setup?plan=${sp.id}&view=board`) },
          { id: `suite-plan-safety-${sp.id}`, label: "See it in Safety", onSelect: () => router.push(`${base}/suite/safety/check`) },
        ],
      });
    }
    for (const b of (suitePlansQuery.data?.batches ?? []).slice(0, 15)) {
      items.push({
        id: `suite-batch-${b.id}`,
        label: b.name,
        group: "Batch plans",
        keywords: ["batch", "change", "bulk", b.tool ?? ""],
        detail: `Change batch${b.tool ? ` · ${b.tool}` : ""}`,
        onSelect: () => router.push(b.tool ? `${base}/suite/change/${b.tool}?batch=${b.id}` : `${base}/suite/change`),
      });
    }
    for (const r of (runsQuery.data ?? []).slice(0, 10)) {
      items.push({
        id: `run-${r.id}`,
        label: `Script run ${r.id.slice(0, 8)} · ${r.status}`,
        group: "Past runs",
        keywords: ["run", "history", r.status],
        detail: r.error ? r.error.slice(0, 120) : `${r.write_count ?? 0} writes`,
        onSelect: () => router.push(`${base}/script-runner?run=${r.id}`),
      });
    }
    for (const snap of (historyQuery.data ?? []).slice(0, 10)) {
      items.push({
        id: `history-${snap.id}`,
        label: snap.label || snap.resource_key,
        group: "History",
        keywords: ["history", "undo", snap.resource_type, snap.resource_key],
        detail: `${snap.reversible === "yes" ? "Can be undone" : snap.reversible === "partial" ? "Partly undoable" : "Cannot be undone"}${snap.created_at ? ` · ${new Date(snap.created_at).toLocaleString()}` : ""}`,
        onSelect: () => router.push(`${base}/journal?change=${encodeURIComponent(snap.id)}`),
      });
    }
    items.push({
      id: "open-expert",
      label: "Open Odoo Expert",
      group: "Expert",
      keywords: ["ask", "help", "ai"],
      onSelect: () => openExpert(),
    });
    for (const prompt of suggestedPromptsQuery.data ?? []) {
      items.push({
        id: `expert-prompt-${prompt.id}`,
        label: prompt.label,
        group: "Expert prompts",
        keywords: [prompt.question],
        onSelect: () => openExpert({ question: prompt.question, autoSubmit: true, freshThread: true }),
      });
    }
    return items;
  }, [
    connectionId,
    modelsQuery.data,
    menusQuery.data,
    automationsQuery.data,
    runsQuery.data,
    suitePlansQuery.data,
    historyQuery.data,
    connectionsQuery.data,
    openExpert,
    router,
    suggestedPromptsQuery.data,
  ]);

  const dynamicCommandItems = useMemo(() => {
    const hits = nlSearchQuery.data?.hits ?? [];
    return hits.map((hit) => ({
      id: hit.id,
      label: hit.label,
      group: hit.kind === "expert" ? "Expert search" : hit.kind === "record" ? "Records" : "Search",
      keywords: [hit.description, hit.expert_question ?? ""],
      detail: hit.description,
      onSelect: () => {
        if (hit.href && /^https?:\/\//.test(hit.href)) {
          window.open(hit.href, "_blank", "noopener,noreferrer");
          return;
        }
        if (hit.href) {
          router.push(hit.href);
          return;
        }
        if (hit.expert_question) {
          openExpert({ question: hit.expert_question, autoSubmit: true, freshThread: true });
        }
      },
    }));
  }, [nlSearchQuery.data, openExpert, router]);

  const connection = connectionQuery.data;
  const connections = connectionsQuery.data ?? [];

  if (!connectionId) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <Callout variant="danger" title="Invalid connection URL">
          Open a connection from the home page or pick one from your saved connections list.
        </Callout>
      </div>
    );
  }

  if (connectionQuery.isPending) {
    return (
      <div className="flex min-h-screen bg-background" role="status" data-testid="app-shell-loading">
        <span className="sr-only">Loading this connection.</span>
        <div
          className="hidden w-60 shrink-0 flex-col gap-2 border-r border-border-subtle bg-surface-raised p-3 md:flex"
          aria-hidden
        >
          <Skeleton className="mb-3 h-8 w-40" />
          {Array.from({ length: 8 }, (_, i) => (
            <Skeleton key={i} className="h-7 w-full" />
          ))}
        </div>
        <div className="flex min-w-0 flex-1 flex-col">
        <OfflineBand />
          <div className="flex h-12 items-center gap-3 border-b border-border-subtle px-4" aria-hidden>
            <Skeleton className="h-6 w-40" />
            <Skeleton className="ml-auto h-6 w-24" />
          </div>
          <div className="flex-1 space-y-4 p-4 md:p-6">
            <div className="space-y-4" aria-hidden>
              <Skeleton className="h-8 w-56" />
              <Skeleton className="h-4 w-80 max-w-full" />
              <Skeleton className="h-40 w-full" />
            </div>
            {slowLoad ? (
              <p className="max-w-md text-sm text-muted">
                Still waiting — check the API is running on port 8001{" "}
                <code className="text-xs">(uv run uvicorn app.main:app --port 8001)</code>.
              </p>
            ) : null}
          </div>
        </div>
      </div>
    );
  }

  if (connectionQuery.isError || !connection) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        <Callout variant="danger" title="Could not load connection">
          <p className="text-sm">
            {connectionQuery.error instanceof Error
              ? connectionQuery.error.message
              : "Check the API is running and this connection still exists."}
          </p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="mt-3"
            onClick={() => void connectionQuery.refetch()}
          >
            Retry
          </Button>
        </Callout>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background" data-testid="app-shell">
      <FaviconBridge />
      <ShortcutSheet />
      {connection && isTestCopy(connection) ? <div className="hazard-band" aria-hidden="true" data-testid="test-copy-band" /> : null}
      <Sidebar connection={connection} connections={connections} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar connection={connection} connections={connections} pathname={pathname} />
        {offline ? (
          <div className="border-b border-warning/30 bg-warning-subtle px-4 py-2 text-sm text-warning">
            You appear to be offline. Changes that need Odoo will fail until connectivity returns.
          </div>
        ) : null}
        <main className="flex-1 overflow-auto bg-background p-4 md:p-6"><PageMove>{children}</PageMove></main>
      </div>
      <ExpertPanel />
      <ExpertBubble />
      <ExpertDiagnoseListener />
      <CommandPalette
        open={commandOpen}
        onOpenChange={(open) => {
          setCommandOpen(open);
          if (!open) setCommandSearch("");
        }}
        items={commandItems}
        dynamicItems={dynamicCommandItems}
        onSearchChange={setCommandSearch}
      />
    </div>
  );
}
